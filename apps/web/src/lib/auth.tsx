"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAccount, useDisconnect, useSignMessage, useSwitchChain } from "wagmi";
import { api, demoLogin, getStoredUser, logout as clearSession, type User } from "@/lib/api";
import { INJECTIVE_CHAIN_ID } from "@/lib/chain";

type AuthContextValue = {
  user: User | null;
  busy: boolean;
  error: string | null;
  /** Sign Arena64 login message with connected wallet and store JWT. */
  loginWithWallet: () => Promise<User>;
  /** Dev-only demo session (API rejects outside development). */
  loginDemo: () => Promise<User>;
  logout: () => void;
  setUser: (u: User | null) => void;
  refreshUser: () => Promise<User | null>;
  shortAddress: string | null;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function shorten(addr: string) {
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { address, isConnected, chainId } = useAccount();
  const { signMessageAsync } = useSignMessage();
  const { switchChainAsync } = useSwitchChain();
  const { disconnect } = useDisconnect();

  useEffect(() => {
    setUser(getStoredUser());
  }, []);

  // If wallet changes while logged in, clear session so they must re-sign
  useEffect(() => {
    if (!user || !address) return;
    if (user.wallet_address.toLowerCase() !== address.toLowerCase()) {
      clearSession();
      setUser(null);
    }
  }, [address, user]);

  const loginWithWallet = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      if (!address || !isConnected) {
        throw new Error("Connect a wallet first");
      }
      if (chainId !== INJECTIVE_CHAIN_ID) {
        try {
          await switchChainAsync({ chainId: INJECTIVE_CHAIN_ID });
        } catch {
          throw new Error(
            `Switch to Injective EVM (chain ${INJECTIVE_CHAIN_ID}) in your wallet, then try again.`
          );
        }
      }

      const nonce = await api<{ message: string; nonce: string }>(
        `/api/auth/nonce?wallet_address=${address}`
      );
      const signature = await signMessageAsync({ message: nonce.message });
      const data = await api<{ access_token: string; user: User }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          wallet_address: address,
          signature,
          message: nonce.message,
          display_name: shorten(address),
        }),
      });
      localStorage.setItem("arena64_token", data.access_token);
      localStorage.setItem("arena64_user", JSON.stringify(data.user));
      setUser(data.user);
      return data.user;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      throw e;
    } finally {
      setBusy(false);
    }
  }, [address, isConnected, chainId, signMessageAsync, switchChainAsync]);

  const loginDemo = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const { user: u } = await demoLogin();
      setUser(u);
      return u;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      throw e;
    } finally {
      setBusy(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    disconnect();
  }, [disconnect]);

  const refreshUser = useCallback(async () => {
    if (!getStoredUser() && !localStorage.getItem("arena64_token")) return null;
    try {
      const u = await api<User>("/api/users/me");
      localStorage.setItem("arena64_user", JSON.stringify(u));
      setUser((prev) => {
        if (
          prev &&
          prev.id === u.id &&
          prev.usdc_balance === u.usdc_balance &&
          prev.available_usdc === u.available_usdc &&
          prev.locked_usdc === u.locked_usdc &&
          prev.coach_credits === u.coach_credits &&
          prev.xp === u.xp &&
          prev.fair_play_score === u.fair_play_score &&
          prev.display_name === u.display_name
        ) {
          return prev;
        }
        return u;
      });
      return u;
    } catch {
      return getStoredUser();
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      busy,
      error,
      loginWithWallet,
      loginDemo,
      logout,
      setUser,
      refreshUser,
      shortAddress: user?.wallet_address ? shorten(user.wallet_address) : address ? shorten(address) : null,
    }),
    [user, busy, error, loginWithWallet, loginDemo, logout, refreshUser, address]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
