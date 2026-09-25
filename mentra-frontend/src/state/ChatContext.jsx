import { createContext, useCallback, useContext, useRef, useState } from "react"
import { conversationApi } from "../api/index.js"
import { useMentraData } from "./MentraDataContext.jsx"

const ChatContext = createContext(null)
// Single conversation for MVP (one goal, one thread). "current" is resolved
// server-side to the signed-in user's one conversation (creating it on first
// use) — see backend/app/core/resolvers.py.
const CONVERSATION_ID = "current"

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState("idle") // idle | loading | sending | error
  const [error, setError] = useState(null)
  const { patchTaskFromChat } = useMentraData()
  // Tracks the most recent failed send so a retry can resend the *same*
  // optimistic bubble instead of appending a duplicate one.
  const lastFailedRef = useRef(null)

  const loadMessages = useCallback(async () => {
    setStatus("loading"); setError(null)
    try {
      const data = await conversationApi.getMessages(CONVERSATION_ID)
      setMessages(data)
      setStatus("success")
    } catch (e) {
      setStatus("error"); setError("Couldn\u2019t load the conversation.")
    }
  }, [])

  const sendMessage = useCallback(async (text, taskId, { retryId } = {}) => {
    const messageId = retryId || `local-${Date.now()}`
    if (!retryId) {
      const optimistic = { id: messageId, sender: "user", content: text, created_at: new Date().toISOString() }
      setMessages((m) => [...m, optimistic])
    }
    setStatus("sending"); setError(null)
    try {
      const { reply, task_update } = await conversationApi.sendMessage(CONVERSATION_ID, text, taskId)
      setMessages((m) => [...m, { id: `ai-${Date.now()}`, sender: "ai", content: reply, created_at: new Date().toISOString() }])
      if (task_update) patchTaskFromChat(task_update.task_id, task_update.status)
      setStatus("success")
      lastFailedRef.current = null
    } catch (e) {
      setStatus("error"); setError("That message didn\u2019t send — you can try again.")
      lastFailedRef.current = { id: messageId, text, taskId }
    }
  }, [patchTaskFromChat])

  // Resends whatever failed last, reusing its optimistic bubble id rather
  // than pushing a new one — fixes the "retry creates a duplicate message"
  // bug.
  const retryLastMessage = useCallback(() => {
    const failed = lastFailedRef.current
    if (!failed) return
    sendMessage(failed.text, failed.taskId, { retryId: failed.id })
  }, [sendMessage])

  return (
    <ChatContext.Provider value={{ messages, status, error, loadMessages, sendMessage, retryLastMessage }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  return useContext(ChatContext)
}
