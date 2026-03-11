# AI Event Generation

## Env

Set these variables in `backend/.env`:

- `OPENAI_API_KEY` - required for generation.
- `OPENAI_MODEL` - default `gpt-5-mini`.
- `AI_DEFAULT_SOURCE_URLS` - comma-separated fallback URLs when the admin form leaves source URLs empty.
- `AI_EVENT_GENERATION_MAX_COUNT` - hard cap for one batch.
- `AI_BOT_EMAIL` and `AI_BOT_HANDLE` - synthetic user for initial AI seed positions.

## Operator Flow

1. Open a browser and collect 2-5 URLs with current, resolvable catalysts.
2. Prefer official or near-official sources: Reuters, government statistics calendars, central bank calendars, company investor relations, exchange calendars, election commission pages, sports league schedules.
3. If a site blocks automatic fetching, paste a short note or excerpt from the browser into the admin form instead.
4. Avoid rumor pages, opinion pieces, sensational headlines, and sources without a clear resolution endpoint.
5. In the admin page, first run AI generation without publish enabled.
6. Review the returned candidates: title clarity, `source_of_truth`, resolution window, AI rationale, and recommended side.
7. Re-run with publish enabled once the batch looks clean.
8. Published AI candidates are created in `pending_review`, not opened immediately. Approve them from the admin moderation queue.
9. If the market is empty, use AI seed positions only after the event has passed moderation and is actually open.

## Selection Rules

Choose events that score well on all four dimensions:

- Resolvability: one clear source can settle the event.
- Timeliness: closes soon enough to feel active, but not so soon that users miss it.
- Relevance: broad enough that even a small audience can understand it.
- Safety: no graphic harm, death, private individuals, illegal activity, or vague culture-war bait.

Good candidates:

- `Will US CPI YoY print below 2.9% on the next release?`
- `Will the Fed hold rates unchanged at the next meeting?`
- `Will Apple report revenue above consensus next earnings release?`

Bad candidates:

- vague political drama without official resolution
- celebrity gossip
- events requiring subjective interpretation
- anything tied to real-money speculation or harmful content

## Notes

- Published AI events are created by the admin account but still enter `pending_review` so they are reviewed before going live.
- AI seed positions are placed by the configured bot user, not by the admin.
- This flow is meant to bootstrap liquidity while the platform has low activity. As real users arrive, use it less aggressively.