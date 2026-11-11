import type { NextConfig } from "next"
import path from "node:path"

const nextConfig: NextConfig = {
  turbopack: { root: path.resolve(__dirname) },
  transpilePackages: ["three"],
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  async rewrites() {
    const target = process.env.BACKEND_URL ||
      (process.env.NODE_ENV !== "production" ? "http://localhost:8000" : undefined)
    if (!target) return {}
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination: `${target}/api/:path*`,
        },
        {
          source: "/health",
          destination: `${target}/health`,
        },
      ],
    }
  },
}

export default nextConfig
