import { describe, expect, it, vi } from 'vitest'
import config from '../../next.config'

describe('backend rewrites', () => {
  it('uses the configured isolated backend in development', async () => {
    vi.stubEnv('NODE_ENV', 'development')
    vi.stubEnv('BACKEND_URL', 'http://127.0.0.1:8385')
    expect(await config.rewrites!()).toEqual({ fallback: [
      { source: '/api/:path*', destination: 'http://127.0.0.1:8385/api/:path*' },
      { source: '/health', destination: 'http://127.0.0.1:8385/health' },
    ] })
  })
  it('keeps the default local development backend', async () => {
    vi.stubEnv('NODE_ENV', 'development')
    vi.stubEnv('BACKEND_URL', '')
    expect(JSON.stringify(await config.rewrites!())).toContain('http://localhost:8000/health')
  })
  it('does not proxy production requests without configuration', async () => {
    vi.stubEnv('NODE_ENV', 'production')
    vi.stubEnv('BACKEND_URL', '')
    expect(await config.rewrites!()).toEqual({})
  })
})
