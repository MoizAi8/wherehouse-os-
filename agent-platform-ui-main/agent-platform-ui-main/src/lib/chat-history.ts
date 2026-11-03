import type { Message } from "@/lib/ai/client"

export type Conversation = {
  id: string
  title: string
  updated: number
  messages?: Message[]
}

export function readChatStorage(key: string): string | null {
  try { return window.localStorage.getItem(key) } catch { return null }
}

export function writeChatStorage(key: string, value: string): boolean {
  try {
    window.localStorage.setItem(key, value)
    return true
  } catch { return false }
}

export function readConversations(key: string, guest: boolean): Conversation[] {
  try {
    const items: unknown = JSON.parse(readChatStorage(key) ?? "[]")
    if (!Array.isArray(items)) return []
    return items.filter((item): item is Conversation =>
      !!item && typeof item.id === "string" && item.id.length <= 64 &&
      typeof item.title === "string" && Number.isFinite(item.updated) &&
      (!guest || item.updated > Date.now() - 30 * 86400000))
      .sort((left, right) => right.updated - left.updated)
      .slice(0, 20)
      .map(item => ({
        id: item.id, title: item.title.slice(0, 64), updated: item.updated,
        ...(guest ? { messages: Array.isArray(item.messages) ? item.messages.filter(
          m => m && typeof m.id === "string" && typeof m.content === "string" &&
            (m.role === "user" || m.role === "assistant"),
        ).slice(-30).map(message => ({ id: message.id, role: message.role, content: message.content.slice(0, 4000) })) : [] } : {}),
      }))
  } catch { return [] }
}

export function newConversationId(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("")
}
