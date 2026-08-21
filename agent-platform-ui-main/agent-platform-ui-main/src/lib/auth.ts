import type { NextAuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt" },
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
          return {
            id: data.user?.id ?? data.id,
            email: data.user?.email ?? data.email,
            name: data.user?.name ?? data.name,
            accessToken: data.access_token,
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
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) session.user.id = (token.id as string) || ""
      session.accessToken = token.accessToken
      return session
    },
  },
}
