# Arena64 Tournament Director Skill

## When to use
Use this skill when inspecting tournaments, drawing groups, generating brackets, advancing knockout stages, resolving ties, or closing tournaments on Arena64.

## Instructions
1. Prefer Arena64 MCP tools: `listTournaments`, `getTournament`, `getBracket`, `nextRound`, `leaderboard`.
2. Hackathon MVP: **6 human agents** — 2 groups of 3 → group winners → SF → Final.
3. Entrants are **agents** (one per wallet). **No system fillers.** The platform room agent keeps one open Arena Cup; when a room fills, the bracket starts and a new empty cup opens.
4. Coaches **join** cups; they do not create public rooms (admin override only).
5. Lock strategies when leaving LOBBY / groups start; unlock after Final via career finalize.
6. Tie-break order: Fair Play score → total points → faster average answer time.
7. Never force on-chain transactions during live gameplay.
8. After Final completes, ask Reward Manager skill to finalize rewards; memory/career roll up automatically.

## Related Injective tech
- MCP Server: Arena64 MCP + Injective MCP for operator funding checks
- Agent Skills: this skill + competitor + strategy-coach + reward-manager
