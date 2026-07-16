# Arena64 Reward Manager Skill

## When to use
Calculate placements, distribute USDC reward pools to Arena64 internal balances, update XP and history.

## Instructions
1. Splits after platform fee: 1st 55%, 2nd 25%, 3rd 12%, 4th 8%.
2. MCP: `claimReward`, `tournamentHistory`, `playerStats`.
3. Credit internal USDC ledger — players may later withdraw/bridge via CCTP flows.
4. Record TournamentHistory for each finisher.

## Injective
- Rewards settle to Arena64 balance funded originally via **CCTP** USDC
- Optional future: claim-to-wallet via Injective MCP `transfer_send`
