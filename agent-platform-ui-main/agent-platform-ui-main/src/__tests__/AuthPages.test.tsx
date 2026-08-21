import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import LoginPage from "@/app/login/page"
import RegisterPage from "@/app/register/page"

vi.mock("next-auth/react", () => ({
  signIn: vi.fn(),
}))

import { signIn } from "next-auth/react"

const mockSignIn = signIn as ReturnType<typeof vi.fn>

describe("Auth pages", () => {
  beforeEach(() => {
    mockSignIn.mockReset()
    mockSignIn.mockResolvedValue({ error: undefined, ok: true })
    vi.stubGlobal("fetch", vi.fn())
  })

  describe("Login page", () => {
    it("shows validation errors for empty fields", async () => {
      render(<LoginPage />)
      fireEvent.click(screen.getByRole("button", { name: /login/i }))
      expect(await screen.findByText("Email is required")).toBeInTheDocument()
      expect(screen.getByText("Password is required")).toBeInTheDocument()
      expect(mockSignIn).not.toHaveBeenCalled()
    })

    it("shows email format error for invalid email", async () => {
      render(<LoginPage />)
      fireEvent.change(screen.getByLabelText("Email"), { target: { value: "not-an-email" } })
      fireEvent.change(screen.getByLabelText("Password"), { target: { value: "whatever" } })
      fireEvent.click(screen.getByRole("button", { name: /login/i }))
      expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument()
      expect(mockSignIn).not.toHaveBeenCalled()
    })

    it("calls signIn with credentials and shows invalid credential error", async () => {
      mockSignIn.mockResolvedValueOnce({ error: "CredentialsSignin", ok: false })
      render(<LoginPage />)
      fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } })
      fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } })
      fireEvent.click(screen.getByRole("button", { name: /login/i }))
      await waitFor(() => expect(mockSignIn).toHaveBeenCalledWith("credentials", {
        email: "user@example.com",
        password: "password123",
        redirect: false,
      }))
      expect(await screen.findByText("Invalid email or password")).toBeInTheDocument()
    })

    it("links to register and forgot password", () => {
      render(<LoginPage />)
      expect(screen.getByRole("link", { name: /create one/i })).toHaveAttribute("href", "/register")
      expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute("href", "/forgot-password")
    })
  })

  describe("Register page", () => {
    it("validates required fields and password mismatch", async () => {
      render(<RegisterPage />)
      fireEvent.click(screen.getByRole("button", { name: /register/i }))
      expect(await screen.findByText("Full name is required")).toBeInTheDocument()
      expect(screen.getByText("Email is required")).toBeInTheDocument()
      expect(screen.getByText("Password is required")).toBeInTheDocument()
      expect(screen.getByText("Please confirm your password")).toBeInTheDocument()
    })

    it("validates password length and mismatch", async () => {
      render(<RegisterPage />)
      fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Test User" } })
      fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } })
      fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } })
      fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "different" } })
      fireEvent.click(screen.getByRole("button", { name: /register/i }))
      expect(await screen.findByText("Password must be at least 8 characters")).toBeInTheDocument()
      expect(screen.getByText("Passwords do not match")).toBeInTheDocument()
    })

    it("posts to register proxy and signs in on success", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ok: true, user: { id: "1", email: "user@example.com" } }),
      })
      vi.stubGlobal("fetch", mockFetch)
      render(<RegisterPage />)
      fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Test User" } })
      fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } })
      fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass123" } })
      fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "StrongPass123" } })
      fireEvent.click(screen.getByRole("button", { name: /register/i }))
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          "/api/auth/register",
          expect.objectContaining({
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: "Test User", email: "user@example.com", password: "StrongPass123" }),
          })
        )
      })
      await waitFor(() => expect(mockSignIn).toHaveBeenCalled())
    })

    it("shows duplicate email error", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ ok: false, error: "Email already registered" }),
      })
      vi.stubGlobal("fetch", mockFetch)
      render(<RegisterPage />)
      fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Test User" } })
      fireEvent.change(screen.getByLabelText("Email"), { target: { value: "dup@example.com" } })
      fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass123" } })
      fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "StrongPass123" } })
      fireEvent.click(screen.getByRole("button", { name: /register/i }))
      expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
      expect(mockSignIn).not.toHaveBeenCalled()
    })

    it("links to login page", () => {
      render(<RegisterPage />)
      expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/login")
    })
  })
})