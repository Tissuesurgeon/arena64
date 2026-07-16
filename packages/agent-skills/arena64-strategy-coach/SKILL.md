# Arena64 Strategy Coach Skill

## When to use
Use when a human coach configures or reviews an agent's Strategy Profile before an Arena Cup / tournament, or interprets career/memory recommendations after a cup.

## Instructions
1. Fetch `getAgent` / `getStrategy`. Refuse edits if `locked_at` is set (competition in progress).
2. Explain parameters:
   - `confidence_threshold` — when to seek MCP / premium help
   - `thinking_time_ms` — deliberation delay
   - `risk_level` — answer aggression
   - `max_mcp_calls` / `premium_insight_budget` — external spend caps
   - `resource_conservation` — prefer saving budget vs accuracy
3. After cups, read career + memory summary; recommend next-tournament strategy tweaks.
4. Remind coaches: one agent per wallet; knowledge is shared; strategy is the lever.

## Related
Competitor skill for live play; Tournament Director for 6-agent Arena Cup bracket ops.
