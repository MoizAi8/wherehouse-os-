"use client"

import { AIAssistant } from "@/components/ai/AIAssistant"
import { motion } from "framer-motion"
import { MessageSquare } from "lucide-react"

export default function ChatPage() {
  return (
    <div className="flex flex-1 flex-col p-6 h-full overflow-hidden">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-center gap-3 mb-6"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg shadow-accent/20">
          <MessageSquare className="h-5 w-5 text-background" />
        </div>
        <div>
          <h1 className="text-base font-semibold tracking-tight text-foreground">Chat</h1>
          <p className="text-xs text-muted-foreground">Ask the AI to manage your warehouse operations</p>
        </div>
      </motion.div>

      <div className="flex-1 flex overflow-hidden min-h-0 rounded-xl border border-border/30 glass-card">
        <AIAssistant />
      </div>
    </div>
  )
}
