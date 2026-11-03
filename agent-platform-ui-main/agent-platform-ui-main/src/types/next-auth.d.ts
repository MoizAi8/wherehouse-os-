import "next-auth"

declare module "next-auth" {
  interface Session {
    demoGuest?: boolean
    accessToken?: string
    error?: "SessionExpired"
    user: {
      id: string
      name?: string | null
      email?: string | null
      image?: string | null
    }
  }

  interface User {
    id: string
    accessToken?: string
    accessTokenExpires?: number
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string
    accessToken?: string
    accessTokenExpires?: number
    error?: "SessionExpired"
  }
}
