# Arena64 on Injective — contracts + judge matrix

## InjFaucet (testnet gas)

One-time **1 INJ** claim per wallet for deposit gas. Owner (`INJ_KEY_EVM`) funds the contract; Arena64 API calls `claimFor(user)`.

### Build

```bash
cd blockchain
forge build
```

### Deploy + fund (Injective EVM testnet, chain 1439)

```bash
export INJ_KEY_EVM=your_deployer_private_key
export INJECTIVE_RPC_URL=https://k8s.testnet.json-rpc.injective.network/

# Deploys InjFaucet and funds with 20 INJ (change amount as needed)
./script/deploy_and_fund.sh 20
```

Or manually:

```bash
forge create src/InjFaucet.sol:InjFaucet \
  --rpc-url "$INJECTIVE_RPC_URL" \
  --private-key "$INJ_KEY_EVM" \
  --broadcast

cast send "$INJ_FAUCET_ADDRESS" "fund()" \
  --value 20ether \
  --rpc-url "$INJECTIVE_RPC_URL" \
  --private-key "$INJ_KEY_EVM"
```

Add to repo root `.env`:

```bash
INJ_KEY_EVM=...          # same key that deployed (owner)
INJ_FAUCET_ADDRESS=0x... # from forge create
```

Never put `INJ_KEY_EVM` in Next.js / Vercel public env.

### API

- `GET /api/faucet/inj/status` — claimed?, balances
- `POST /api/faucet/inj/claim` — auth required; one claim forever

### UI

- `/claim` — Claim 1 INJ page
- Dashboard + nav link

---

## Network

| | Testnet (default) | Mainnet (gated) |
|--|-------------------|-----------------|
| Chain ID | `1439` | `1776` |
| CAIP-2 | `eip155:1439` | `eip155:1776` |
| USDC | `0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d` | `0xa00C59fF5a080D2b954d0c75e46E22a0c371235a` |
| Iris | `iris-api-sandbox.circle.com` | `iris-api.circle.com` |

Set `INJECTIVE_NETWORK=testnet` (default). Do not flip mainnet until the checklist in the root README passes.

## Env / ABI surface

| Variable | Role |
|----------|------|
| `ARENA64_TREASURY_ADDRESS` | Receives ERC-20 USDC deposits |
| `ARENA64_TREASURY_PRIVATE_KEY` | Hot key for withdrawals to coach EOA |
| `INJ_KEY_EVM` | Owner key for InjFaucet `claimFor` |
| `INJ_FAUCET_ADDRESS` | Deployed InjFaucet contract |
| `INJECTIVE_RPC_URL` | EVM RPC for transfer verification |
| `INJECTIVE_USDC_ADDRESS` | USDC contract |
| `X402_FACILITATOR_URL` | Facilitator verify endpoint |
| `X402_REQUIRE_VERIFY` | Enforce facilitator (dev may bypass) |
| `X402_ALLOW_TESTNET_FALLBACK` | Soft-fail verify on testnet only |
| `PREMIUM_INSIGHT_COST_USDC` | Arena64 Account debit per premium call (default 0.05) |
| `SERVICE_API_KEY` | Runtime + MCP service calls |

ERC-20 `Transfer` is verified on deposit; CCTP uses Circle Iris attestation before **Available** credit. If MetaMask returns a phantom hash, use **Sync deposits** (`POST /api/wallet/deposit/sync`) to credit recent wallet→treasury transfers. Entry fees **lock** Available → Locked until settle.

## Demo map

| Integration | UI / API | Notes |
|-------------|----------|-------|
| Wallet connect | `/` → Connect | Coach identity → agent ownership |
| Arena64 Account | `/wallet` or `/dashboard` | **Available** / **Locked** (not an on-chain wallet) |
| Claim testnet INJ | `/claim` | 1 INJ once per wallet via InjFaucet |
| USDC deposit | `/wallet` Fund Account | EOA → Treasury → Available; Sync deposits if needed |
| Withdraw | `POST /api/wallet/withdraw` | Available → EOA (needs treasury key) |
| USDC CCTP | `/wallet` CCTP tab | Bridge in → Available |
| x402 premium | ledger debit + optional proof | Mid-match / coach packs |
| MCP | `apps/mcp-server` | researchByCategory, buyPremiumInsight, getStandings |
| Agent Skills | `packages/agent-skills` | competitor + football research + director |
| Competition runtime | `apps/ai-runtime` | Strategy / Memory / Skill / Decision + budget object |
| Arena Cup | `/tournaments` | Platform opens 6-agent rooms; humans join until full |

## Competition runtime (not a planner)

Arena64 adapts OpenClaw’s modular agent pattern for **competition**:

`Question → Strategy gate → Memory → Decision → optional Skills (≤2) → Re-decide → Experience → Memory Manager`

Equal knowledge and tools; **strategy profiles** differentiate behavior.

Tournament MVP: `Lobby (6) → 2×3 groups → SF → Final`. Platform room agent keeps one open cup; when full, bracket starts and a new empty cup opens. No system fillers.

Finance path:

`Connected Wallet → (optional Claim INJ) → Treasury USDC → Arena64 Account → lock → x402 → settle → withdraw`

## Local demo preference

Use Docker Postgres on host port **15432** (`docker compose up -d postgres redis`). Point `DATABASE_URL` at `localhost:15432`. Remote Render Postgres adds multi-second latency that hurts live agent demos.
