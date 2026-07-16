"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAccount } from "wagmi";
import { ConnectWallet } from "@/components/ConnectWallet";
import { useAuth } from "@/lib/auth";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agent", label: "Agent" },
  { href: "/trial", label: "Practice" },
  { href: "/tournaments", label: "Tournaments" },
  { href: "/world-cup", label: "World Cup" },
  { href: "/claim", label: "Claim INJ" },
  { href: "/wallet", label: "Balance" },
  { href: "/agent/career", label: "Career" },
] as const;

/**
 * DeFi-style shell: brand left; status + Connect/Account (+ menu when connected) far right.
 * Main nav links live in a right drawer, only when a wallet is connected.
 */
export function Nav() {
  const { user } = useAuth();
  const { isConnected } = useAccount();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!isConnected) setMenuOpen(false);
  }, [isConnected]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [menuOpen]);

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-[var(--turf-line)] bg-[rgba(6,16,24,0.78)] backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link
          href="/"
          className="led-title flex shrink-0 items-center gap-2 text-2xl text-[var(--trophy-gold)]"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.svg"
            alt=""
            width={32}
            height={32}
            className="h-8 w-8 rounded-lg"
          />
          <span>Arena64</span>
        </Link>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {user && (
            <Link
              href="/wallet"
              className="hidden border border-[var(--trophy-gold)]/40 px-2 py-1.5 text-xs tracking-widest text-[var(--trophy-gold)] sm:inline"
              title="Arena64 Account · Available"
            >
              {Number(user.available_usdc ?? user.usdc_balance ?? 0).toLocaleString(undefined, {
                maximumFractionDigits: 2,
              })}{" "}
              USDC
            </Link>
          )}
          <ConnectWallet variant="nav" />
          {isConnected && (
            <button
              type="button"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
              className="btn-press btn-tap flex h-9 w-9 flex-col items-center justify-center gap-1.5 border border-[var(--turf-line)] text-[var(--floodlight)] transition hover:border-[var(--trophy-gold)]/50 hover:text-[var(--trophy-gold)]"
            >
              <span className="block h-px w-4 bg-current" />
              <span className="block h-px w-4 bg-current" />
              <span className="block h-px w-4 bg-current" />
            </button>
          )}
        </div>
      </div>

      {isConnected && menuOpen && (
        <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-black/55"
            onClick={() => setMenuOpen(false)}
          />
          <aside className="absolute inset-y-0 right-0 flex w-[min(18rem,88vw)] flex-col border-l border-[var(--turf-line)] bg-[rgba(6,16,24,0.96)] shadow-xl backdrop-blur-md">
            <div className="flex items-center justify-between border-b border-[var(--turf-line)] px-4 py-3">
              <p className="text-xs uppercase tracking-[0.25em] text-[var(--trophy-gold)]">Menu</p>
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setMenuOpen(false)}
                className="px-2 py-1 text-sm text-[var(--floodlight)]/70 hover:text-[var(--floodlight)]"
              >
                ✕
              </button>
            </div>
            <nav className="flex flex-col gap-1 p-3 text-sm uppercase tracking-wider text-[var(--floodlight)]/80">
              {NAV_LINKS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMenuOpen(false)}
                  className="border border-transparent px-3 py-2.5 hover:border-[var(--turf-line)] hover:text-[var(--floodlight)]"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
        </div>
      )}
    </header>
  );
}
