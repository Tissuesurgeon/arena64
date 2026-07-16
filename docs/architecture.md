# Architecture overview — see README for diagrams and Injective integration matrix.

Arena64 separates gameplay (JWT + Redis + Postgres) from settlement (CCTP deposits, x402 purchases).

Agents live in `apps/api/app/agents/` and are mirrored as skills under `packages/agent-skills/`.
MCP tools in `apps/mcp-server/` proxy the same REST API.