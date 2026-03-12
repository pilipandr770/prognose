# Social V2 Roadmap

## Goal

Turn the social area from a thin utility layer into a real retention loop.

The current product already has the minimum building blocks:

- public profiles
- follow and unfollow
- activity feed for followed users
- prediction and portfolio leaderboards

What is still missing is a stronger answer to three questions:

- who should I follow?
- why should I come back?
- what makes another user's profile worth opening?

## Product Principles

Social features should reinforce the two core product loops, not distract from them.

- social should help users discover better people, events, and strategies
- social should create reasons to return even when the user is not placing a trade right now
- social should preserve privacy rules, especially private portfolio holdings
- social should reward trustworthy creators and accurate users

## Implementation Order

### Iteration 1. Discovery + Better Feed

Goal: improve retention and discovery with minimal schema complexity.

Scope:

- richer feed with more than one activity type
- suggested users section
- visible following list with quick unfollow
- top prediction users block
- top portfolio users block
- stronger public profile rendering on the frontend

Why this comes first:

- highest product value per unit of engineering effort
- mostly uses existing data: follows, events, predictions, leaderboards
- no heavy notification or comment system required yet

### Iteration 2. Notifications and Social Inbox

Goal: create a direct re-engagement loop.

Scope:

- in-app notifications inbox
- follow notifications
- moderation result notifications for creators
- event closing soon notifications for followed events
- event resolved notifications for user positions

### Iteration 3. Social Objects Around Content

Goal: make social interaction attach to events and predictions, not only to user handles.

Scope:

- save event
- follow event
- lightweight reactions
- public creator activity around approved events

### Iteration 4. Trust and Reputation Layer

Goal: improve feed quality and creator credibility.

Scope:

- badges for trusted creator / top predictor / top portfolio
- clearer verification status in social surfaces
- moderation-aware visibility rules for suspicious accounts

## Iteration 1 Backend Plan

- expand `social_service` to return multiple feed item types
- add discovery endpoint powered by leaderboard snapshots and existing activity counts
- enrich public profile payload with creator-oriented metrics
- keep portfolio privacy rules intact

## Iteration 1 Frontend Plan

- redesign social page around sections instead of raw forms
- add recommended and leaderboard-based user cards
- add following list with quick unfollow action
- improve feed cards with different rendering by item type
- replace raw profile JSON with a readable public profile card

## Success Criteria For Iteration 1

- a new user can discover multiple relevant accounts without manually typing a handle
- the social page shows at least four useful surfaces: following, suggested users, top prediction users, top portfolio users
- the feed reflects more than one public action type
- users can follow and unfollow without leaving the page

## Out Of Scope For This Iteration

- comments
- direct messaging
- push notifications
- email notifications
- copy trading
- public portfolio holdings
