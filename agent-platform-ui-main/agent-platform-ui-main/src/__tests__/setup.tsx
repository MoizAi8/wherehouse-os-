import "@testing-library/jest-dom"

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <div {...rest}>{children}</div>,
    span: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <span {...rest}>{children}</span>,
    tr: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <tr {...rest}>{children}</tr>,
    nav: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <nav {...rest}>{children}</nav>,
    button: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <button {...rest}>{children}</button>,
    header: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <header {...rest}>{children}</header>,
    p: ({ children, ...rest }: { children: React.ReactNode; [key: string]: unknown }) => <p {...rest}>{children}</p>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useScroll: () => ({ scrollYProgress: { on: vi.fn() } }),
  useSpring: (v: unknown) => v,
  useTransform: (v: unknown) => v,
}))

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn().mockResolvedValue(null),
    post: vi.fn().mockResolvedValue(null),
    put: vi.fn().mockResolvedValue(null),
    patch: vi.fn().mockResolvedValue(null),
    delete: vi.fn().mockResolvedValue(null),
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message)
      this.name = "ApiError"
    }
  },
}))

vi.mock("@/contexts/SearchContext", () => ({
  SearchProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useSearch: () => ({ query: "", setQuery: vi.fn() }),
}))

class MockIntersectionObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
vi.stubGlobal("IntersectionObserver", MockIntersectionObserver)

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})
