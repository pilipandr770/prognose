import math
from decimal import Decimal, ROUND_HALF_UP

from app.models.prediction import PredictionPosition


DEFAULT_LMSR_LIQUIDITY = Decimal("375.00")


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 6)))


def _quantize(value: Decimal, pattern: str) -> Decimal:
    return Decimal(value).quantize(Decimal(pattern), rounding=ROUND_HALF_UP)


def _current_inventory(event) -> dict[int, Decimal]:
    inventory_by_outcome_id: dict[int, Decimal] = {outcome.id: Decimal("0.00") for outcome in event.outcomes}
    positions = PredictionPosition.query.filter_by(event_id=event.id).all()
    for position in positions:
        quantity = Decimal(position.share_quantity or 0)
        if quantity <= Decimal("0.00"):
            quantity = Decimal(position.stake_amount)
        inventory_by_outcome_id[position.outcome_id] = inventory_by_outcome_id.get(position.outcome_id, Decimal("0.00")) + quantity
    return inventory_by_outcome_id


def _cost(inventory: dict[int, Decimal], outcome_ids: list[int], liquidity: Decimal) -> Decimal:
    liquidity_float = max(float(liquidity), 1.0)
    exponentials = [math.exp(float(inventory[outcome_id]) / liquidity_float) for outcome_id in outcome_ids]
    return Decimal(str(liquidity_float * math.log(sum(exponentials))))


def quote_lmsr_trade(event, *, outcome_id: int, budget: Decimal, liquidity_parameter: Decimal | None = None) -> dict:
    normalized_budget = Decimal(budget)
    if normalized_budget <= Decimal("0.00"):
        raise ValueError("budget must be greater than zero.")

    liquidity = Decimal(liquidity_parameter or event.market_liquidity or DEFAULT_LMSR_LIQUIDITY)
    outcome_ids = [outcome.id for outcome in event.outcomes]
    if outcome_id not in outcome_ids:
        raise ValueError("Outcome does not belong to the event.")

    inventory = _current_inventory(event)
    current_cost = _cost(inventory, outcome_ids, liquidity)

    low = Decimal("0.00")
    high = normalized_budget * Decimal("10.0")
    while _cost({**inventory, outcome_id: inventory[outcome_id] + high}, outcome_ids, liquidity) - current_cost < normalized_budget:
        high *= Decimal("2.0")
        if high > Decimal("1000000.00"):
            break

    for _ in range(80):
        midpoint = (low + high) / Decimal("2.0")
        simulated_inventory = {**inventory, outcome_id: inventory[outcome_id] + midpoint}
        simulated_cost = _cost(simulated_inventory, outcome_ids, liquidity)
        if simulated_cost - current_cost <= normalized_budget:
            low = midpoint
        else:
            high = midpoint

    share_quantity = _quantize(low, "0.000001")
    average_price = _quantize(normalized_budget / share_quantity, "0.000001") if share_quantity > Decimal("0.00") else Decimal("0.00")
    post_trade_inventory = {**inventory, outcome_id: inventory[outcome_id] + share_quantity}
    post_trade_state = compute_lmsr_market_state(event, liquidity_parameter=liquidity, inventory_override=post_trade_inventory)

    return {
        "budget": str(_quantize(normalized_budget, "0.01")),
        "share_quantity": str(share_quantity),
        "average_price": str(average_price),
        "post_trade_market_state": post_trade_state,
    }


def compute_lmsr_market_state(event, *, liquidity_parameter: Decimal | None = None, inventory_override: dict[int, Decimal] | None = None) -> dict | None:
    if not event.outcomes:
        return None

    liquidity = Decimal(liquidity_parameter or DEFAULT_LMSR_LIQUIDITY)
    normalized_liquidity = max(float(liquidity), 1.0)

    inventory_by_outcome_id = inventory_override or _current_inventory(event)

    scaled_values = [math.exp(float(inventory_by_outcome_id[outcome.id]) / normalized_liquidity) for outcome in event.outcomes]
    denominator = sum(scaled_values) or 1.0

    outcomes = []
    for outcome, scaled_value in zip(event.outcomes, scaled_values):
        probability = scaled_value / denominator
        outcomes.append(
            {
                "id": outcome.id,
                "label": outcome.label,
                "position": outcome.position,
                "inventory": str(_quantize(inventory_by_outcome_id[outcome.id], "0.000001")),
                "price": _to_decimal(probability),
                "probability_pct": _to_decimal(probability * 100),
            }
        )

    return {
        "algorithm": "LMSR",
        "liquidity_parameter": str(liquidity),
        "total_volume": str(_quantize(sum(inventory_by_outcome_id.values(), Decimal("0.00")), "0.000001")),
        "outcomes": outcomes,
    }