#!/usr/bin/env bash
# Deploy InjFaucet to Injective EVM testnet and optionally fund it.
# Usage (from repo root or blockchain/):
#   export INJ_KEY_EVM=...
#   export INJECTIVE_RPC_URL=https://k8s.testnet.json-rpc.injective.network/
#   ./script/deploy_and_fund.sh [fund_amount_inj]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RPC="${INJECTIVE_RPC_URL:-https://k8s.testnet.json-rpc.injective.network/}"
KEY="${INJ_KEY_EVM:?Set INJ_KEY_EVM}"
FUND_AMOUNT="${1:-10}"

if [[ "$KEY" != 0x* ]]; then
  KEY="0x$KEY"
fi

echo "Deploying InjFaucet…"
OUT=$(forge create src/InjFaucet.sol:InjFaucet \
  --rpc-url "$RPC" \
  --private-key "$KEY" \
  --broadcast 2>&1)
echo "$OUT"

ADDR=$(echo "$OUT" | sed -n 's/.*Deployed to: \(0x[a-fA-F0-9]\{40\}\).*/\1/p' | tail -1)
if [[ -z "$ADDR" ]]; then
  echo "Could not parse deployed address" >&2
  exit 1
fi

echo "INJ_FAUCET_ADDRESS=$ADDR"
echo "Add that to your .env"

if [[ "$FUND_AMOUNT" != "0" ]]; then
  WEI=$(python3 -c "print(int(float('$FUND_AMOUNT') * 10**18))")
  echo "Funding faucet with ${FUND_AMOUNT} INJ…"
  cast send "$ADDR" "fund()" \
    --value "${WEI}wei" \
    --rpc-url "$RPC" \
    --private-key "$KEY"
  echo "Funded."
fi
