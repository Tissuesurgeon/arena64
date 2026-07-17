/** @type {import('next').NextConfig} */

function resolveApiOrigin() {
  const pub = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "");
  if (pub.startsWith("http") && !/localhost|127\.0\.0\.1/.test(pub)) {
    return pub;
  }
  const explicit = (process.env.ARENA64_API_ORIGIN || "").trim().replace(/\/+$/, "");
  if (explicit) return explicit;
  // Vercel build: default to the Arena64 Railway production API
  if (process.env.VERCEL) {
    return "https://arena64-production.up.railway.app";
  }
  return "http://127.0.0.1:8000";
}

const apiOrigin = resolveApiOrigin();

const nextConfig = {
  reactStrictMode: true,
  // Enabled only for container builds (Docker). Vercel uses the default output.
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" } : {}),
  // When Vercel Root Directory is the monorepo root, emit `.next` at repo root
  // so the Next.js builder can find the build output. Prefer Root Directory = apps/web.
  ...(process.env.ARENA64_BUILD_FROM_ROOT === "1" ? { distDir: "../../.next" } : {}),
  // Browser calls /arena-api/* → Railway (avoids CORS + wrong localhost NEXT_PUBLIC_API_URL)
  async rewrites() {
    return [
      {
        source: "/arena-api/:path*",
        destination: `${apiOrigin}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
