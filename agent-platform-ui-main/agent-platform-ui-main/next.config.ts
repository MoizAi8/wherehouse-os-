import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  transpilePackages: ["three"],
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  async rewrites() {
    if (process.env.NODE_ENV === "production") return {}
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
        {
          source: "/health",
          destination: "http://localhost:8000/health",
        },
      ],
    }
  },
}

export default nextConfig
