---
description: x402 premium insight spend when strategy allows
---

# Arena64 Premium Insight Skill

## When to use
When confidence is below threshold, `premium_insight_budget` remains, and resource_conservation is low (analyst / balanced styles).

## Instructions
1. Strategy Engine must allow premium before calling `buyPremiumInsight`.
2. Decrement premium budget after a successful call.
3. Re-decide with insight text in tool_results.
