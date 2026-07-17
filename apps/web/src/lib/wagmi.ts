"use client";

import { http, createConfig } from "wagmi";
// Import specific connectors — barrel `wagmi/connectors` pulls Tempo and breaks Next.
// Use `injected` only — wagmi's `metaMask` connector needs optional peer
// `@metamask/connect-evm`, which breaks Vercel builds when missing.
import { injected } from "wagmi/connectors/injected";
import { walletConnect } from "wagmi/connectors/walletConnect";
import { injectiveEvm } from "./chain";

const connectors = [injected({ shimDisconnect: true })];
const wcId =
  process.env.NEXT_PUBLIC_WC_PROJECT_ID ||
  process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID;
if (wcId) {
  connectors.push(
    walletConnect({
      projectId: wcId,
      showQrModal: true,
    })
  );
}

export const wagmiConfig = createConfig({
  chains: [injectiveEvm],
  connectors,
  transports: {
    [injectiveEvm.id]: http(injectiveEvm.rpcUrls.default.http[0]),
  },
  ssr: true,
});
