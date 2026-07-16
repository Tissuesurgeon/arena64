# Arena64 Puzzle Generator Skill

## When to use
Generate or select football knowledge and memory challenges for Arena64 rounds.

## Instructions
1. Prefer the DB question bank populated by the **Web Scout** agent (`source=web_scout`) plus any approved seed questions.
2. Modes: FOOTBALL (20s MCQ) and MEMORY (10s fact card → MCQ).
3. Balance difficulty across a round; avoid repeating question IDs in the same match.
4. Never expose correct answers to clients — server validates only.
5. Do not call external football data APIs. If the bank is thin, run Web Scout (`POST /api/admin/scout/run`).

## Related
- Web Scout scrapes allowlisted pages → knowledge_entries → questions
- Tournament Director starts matches after questions are selected
- Fair Play monitors anomalous perfect scores
