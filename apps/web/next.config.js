/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Enabled only for container builds (Docker). Vercel uses the default output.
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" } : {}),
  // When Vercel Root Directory is the monorepo root, emit `.next` at repo root
  // so the Next.js builder can find the build output. Prefer Root Directory = apps/web.
  ...(process.env.ARENA64_BUILD_FROM_ROOT === "1" ? { distDir: "../../.next" } : {}),
};

module.exports = nextConfig;
