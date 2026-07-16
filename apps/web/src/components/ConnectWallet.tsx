"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAccount, useConnect, useDisconnect } from "wagmi";
import { useAuth } from "@/lib/auth";
import { INJECTIVE_CHAIN_ID } from "@/lib/chain";

type Props = {
  /** Compact for nav; full for landing / login panel */
  variant?: "nav" | "hero";
  className?: string;
};

/**
 * DeFi-style far-right control:
 * - Disconnected → Connect Wallet
 * - Connected + signed in → single address chip → menu (Profile / Exit)
 */
export function ConnectWallet({ variant = "nav", className = "" }: Props) {
  const { address, isConnected, chainId } = useAccount();
  const { connectors, connectAsync, isPending: connecting } = useConnect();
  const { disconnect } = useDisconnect();
  const { user, busy, error, loginWithWallet, loginDemo, logout, shortAddress } = useAuth();
  const [open, setOpen] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const wrongChain = isConnected && chainId != null && chainId !== INJECTIVE_CHAIN_ID;

  async function onConnect(connectorId: string) {
    setLocalError(null);
    try {
      const connector = connectors.find((c) => c.uid === connectorId || c.id === connectorId);
      if (!connector) throw new Error("Wallet not available");
      await connectAsync({ connector, chainId: INJECTIVE_CHAIN_ID });
      setOpen(false);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onSignIn() {
    setLocalError(null);
    try {
      await loginWithWallet();
      setOpen(false);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onDemo() {
    setLocalError(null);
    try {
      await loginDemo();
      setOpen(false);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!mounted) {
    return (
      <button
        type="button"
        disabled
        className={`border border-[var(--trophy-gold)]/40 px-3 py-1.5 text-[var(--trophy-gold)]/50 ${className}`}
      >
        Connect
      </button>
    );
  }

  // Signed in — single account chip (DeFi pattern)
  if (user) {
    return (
      <div ref={rootRef} className={`relative ${className}`}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="border border-[var(--trophy-gold)]/50 bg-[var(--trophy-gold)]/10 px-3 py-1.5 font-mono text-xs tracking-wider text-[var(--trophy-gold)] transition hover:bg-[var(--trophy-gold)]/20"
          aria-expanded={open}
          aria-haspopup="menu"
        >
          {shortAddress}
        </button>
        {open && (
          <div
            role="menu"
            className="absolute right-0 z-50 mt-2 min-w-[11rem] border border-[var(--turf-line)] bg-[var(--night-sky)] py-1 shadow-xl"
          >
            <Link
              href="/profile"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block px-4 py-2 text-sm text-[var(--floodlight)]/80 transition hover:bg-white/5 hover:text-[var(--trophy-gold)]"
            >
              Profile
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                logout();
                disconnect();
              }}
              className="block w-full px-4 py-2 text-left text-sm text-[var(--floodlight)]/60 transition hover:bg-white/5 hover:text-[var(--whistle-red)]"
            >
              Exit
            </button>
          </div>
        )}
      </div>
    );
  }

  const btnClass =
    variant === "hero"
      ? "btn-press btn-tap bg-[var(--trophy-gold)] px-8 py-3 font-display text-xl tracking-wider text-[var(--night-sky)] transition hover:brightness-110"
      : "btn-press btn-tap border border-[var(--trophy-gold)] px-3 py-1.5 text-sm text-[var(--trophy-gold)] transition hover:bg-[var(--trophy-gold)] hover:text-[var(--night-sky)]";

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={busy || connecting}
        onClick={() => setOpen((v) => !v)}
        className={btnClass}
      >
        {busy || connecting ? "Connecting…" : isConnected ? "Sign in" : "Connect Wallet"}
      </button>

      {open && (
        <div
          className={`absolute right-0 z-50 mt-2 min-w-[16rem] border border-[var(--turf-line)] bg-[var(--night-sky)] p-3 shadow-xl ${
            variant === "hero" ? "left-0 right-auto" : ""
          }`}
        >
          <p className="mb-2 text-[10px] uppercase tracking-[0.2em] text-[var(--floodlight)]/45">
            Injective EVM · {INJECTIVE_CHAIN_ID}
          </p>

          {!isConnected && (
            <ul className="space-y-2">
              {connectors.map((c) => (
                <li key={c.uid}>
                  <button
                    type="button"
                    onClick={() => onConnect(c.uid)}
                    className="btn-press btn-tap w-full border border-[var(--turf-line)] px-3 py-2 text-left text-sm transition hover:border-[var(--trophy-gold)] hover:text-[var(--trophy-gold)]"
                  >
                    {c.name === "Injected" ? "Browser Wallet" : c.name}
                  </button>
                </li>
              ))}
            </ul>
          )}

          {isConnected && (
            <div className="space-y-2">
              <p className="text-xs text-[var(--floodlight)]/70">
                {address?.slice(0, 6)}…{address?.slice(-4)}
                {wrongChain ? " · wrong network" : ""}
              </p>
              <button
                type="button"
                onClick={onSignIn}
                disabled={busy}
                className="w-full bg-[var(--trophy-gold)] px-3 py-2 text-sm font-semibold text-[var(--night-sky)]"
              >
                Sign Arena64 login
              </button>
              <button
                type="button"
                onClick={() => disconnect()}
                className="w-full text-xs text-[var(--floodlight)]/50 hover:text-[var(--whistle-red)]"
              >
                Disconnect wallet
              </button>
            </div>
          )}

          <div className="mt-3 border-t border-[var(--turf-line)] pt-2">
            <button
              type="button"
              onClick={onDemo}
              disabled={busy}
              className="w-full text-left text-xs text-[var(--floodlight)]/40 transition hover:text-[var(--floodlight)]/70"
            >
              Continue with demo session
            </button>
          </div>

          {(localError || error) && (
            <p className="mt-2 text-xs text-[var(--whistle-red)]">{localError || error}</p>
          )}
        </div>
      )}
    </div>
  );
}
