import type { Metadata } from "next";
import { Bebas_Neue, DM_Sans } from "next/font/google";
import { Nav } from "@/components/Nav";
import { Providers } from "@/components/Providers";
import "@/styles/tokens.css";
import "./globals.css";

const display = Bebas_Neue({ weight: "400", subsets: ["latin"], variable: "--font-display" });
const body = DM_Sans({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "Arena64 — Become the squad",
  description:
    "AI-managed World Cup–inspired arena on Injective. Free trial, live tournaments, football knowledge and memory — skill competition, not betting.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="font-body antialiased">
        <Providers>
          <Nav />
          <main className="min-h-screen pt-14">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
