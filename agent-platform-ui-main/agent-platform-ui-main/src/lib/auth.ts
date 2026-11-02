import type { NextAuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { accessTokenExpiry } from "@/lib/token-expiry"

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt", maxAge: 60 * 60 },
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null

        const apiBase = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL
        if (!apiBase) return null

        try {
          const res = await fetch(`${apiBase}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: credentials.email, password: credentials.password }),
          })

          if (!res.ok) return null

          const data = await res.json()
          const expires = accessTokenExpiry(data.access_token)
          if (!expires || expires <= Date.now() + 5000) return null
          return {
            id: data.user?.id ?? data.id,
            email: data.user?.email ?? data.email,
            name: data.user?.name ?? data.name,
            accessToken: data.access_token,
            accessTokenExpires: expires,
          }
        } catch {
          return null
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = (user.id as string) || ""
        token.accessToken = user.accessToken
        token.accessTokenExpires = user.accessTokenExpires
      }
      // Also handles cookies issued before expiry tracking was introduced.
      const expires = accessTokenExpiry(token.accessToken)
      token.accessTokenExpires = expires
      if (!expires || Date.now() >= expires - 5000) {
        token.accessToken = undefined
        token.error = "SessionExpired"
      } else {
        token.error = undefined
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) session.user.id = (token.id as string) || ""
      session.accessToken = token.accessToken
      session.error = token.error
      if (token.accessTokenExpires) {
        session.expires = new Date(token.accessTokenExpires).toISOString()
      }
      return session
    },
  },
}
