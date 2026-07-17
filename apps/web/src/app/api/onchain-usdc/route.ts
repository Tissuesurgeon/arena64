import { NextRequest, NextResponse } from "next/server";

/**
 * Same-origin USDC balance proxy (Injective EVM).
 * Avoids browser→RPC flakes and does not require Arena64 JWT.
 *
 * Docs: https://docs.injective.network/developers-defi/usdc-stablecoin
 */

const USDC_TESTNET = "0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d";
const USDC_MAINNET = "0xa00C59fF5a080D2b954d0c75e46E22a0c371235a";

const RPCS = [
  process.env.NEXT_PUBLIC_RPC_URL,
  "https://k8s.testnet.json-rpc.injective.network/",
  "https://testnet.evm.archival.chain.virtual.json-rpc.injective.network/",
].filter((u): u is string => Boolean(u && u.trim()));

function isAddress(v: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test(v);
}

async function ethCall(rpc: string, to: string, data: string): Promise<string> {
  const res = await fetch(rpc, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "eth_call",
      params: [{ to, data }, "latest"],
    }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`RPC HTTP ${res.status}`);
  const json = (await res.json()) as { result?: string; error?: { message?: string } };
  if (json.error) throw new Error(json.error.message || "RPC error");
  if (!json.result) throw new Error("empty eth_call result");
  return json.result;
}

export async function GET(req: NextRequest) {
  const address = (req.nextUrl.searchParams.get("address") || "").trim();
  if (!isAddress(address)) {
    return NextResponse.json({ detail: "Valid 0x address required" }, { status: 400 });
  }

  const chainId = Number(process.env.NEXT_PUBLIC_CHAIN_ID || 1439);
  const usdc = chainId === 1776 ? USDC_MAINNET : USDC_TESTNET;
  const data = `0x70a08231${address.slice(2).toLowerCase().padStart(64, "0")}`;

  let lastErr: unknown;
  for (const rpc of RPCS) {
    try {
      const result = await ethCall(rpc, usdc, data);
      const micro = BigInt(result);
      return NextResponse.json({
        wallet_address: address.toLowerCase(),
        usdc_address: usdc,
        balance_usdc: Number(micro) / 1e6,
        balance_micro: micro.toString(),
        chain_id: chainId,
        rpc,
      });
    } catch (e) {
      lastErr = e;
    }
  }

  return NextResponse.json(
    {
      detail: "Could not read on-chain USDC balance",
      error: lastErr instanceof Error ? lastErr.message : String(lastErr),
    },
    { status: 502 }
  );
}
