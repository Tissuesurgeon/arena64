/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Enabled only for container builds (Docker). Vercel uses the default output.
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" } : {}),
};

module.exports = nextConfig;
