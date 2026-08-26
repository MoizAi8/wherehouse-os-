import { defineConfig } from "vitest/config"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export default defineConfig({
  test: {
    environment: "happy-dom",
    setupFiles: ["./src/__tests__/setup.tsx"],
    globals: true,
    css: true,
    server: {
      deps: {
        inline: []
      }
    },
    pool: "forks",
    maxConcurrency: 1,
    isolate: true,
    restoreMocks: true,
    clearMocks: true,
    unstubEnvs: true,
    testTimeout: 30000,
    hookTimeout: 10000,
    teardownTimeout: 5000,
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["node_modules", "dist", ".next", "out"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      exclude: [
        "node_modules/",
        "src/__tests__/",
        "*.config.*",
        "*.d.ts"
      ]
    }
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@/lib": path.resolve(__dirname, "./src/lib"),
      "@/components": path.resolve(__dirname, "./src/components"),
      "@/hooks": path.resolve(__dirname, "./src/hooks"),
      "@/contexts": path.resolve(__dirname, "./src/contexts"),
      "@/app": path.resolve(__dirname, "./src/app"),
      "@/providers": path.resolve(__dirname, "./src/providers"),
      "@/types": path.resolve(__dirname, "./src/types")
    },
    conditions: ["import", "module", "browser", "default"]
  },
  ssr: {
    noExternal: [],
    external: []
  },
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "next",
      "@testing-library/react",
      "@testing-library/jest-dom",
      "@testing-library/user-event",
      "vitest",
      "happy-dom",
      "react-dom/client",
      "react/jsx-runtime"
    ],
    exclude: [],
    esbuildOptions: {
      target: "es2022",
      supported: {
        "top-level-await": true
      }
    }
  },
  build: {
    target: "es2022",
    sourcemap: true,
    minify: false,
    rollupOptions: {
      external: [],
      output: {
        format: "esm",
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name].[ext]"
      }
    }
  },
  define: {
    "process.env.NODE_ENV": '"test"',
    "process.env.VITEST": '"true"',
    "process.env.NEXT_TELEMETRY_DISABLED": '"1"'
  }
})