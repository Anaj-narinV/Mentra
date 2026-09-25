import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { useChat } from "../../state/ChatContext.jsx"
import { ChatBubble, TypingIndicator, SuggestionChip } from "../../components/chat.jsx"
import { EmptyState, ErrorState } from "../../components/ui.jsx"

const SUGGESTIONS = ["I finished today's task", "I couldn't finish it", "I don't understand this topic", "I need to move today's tasks"]

export default function Chat() {
  const { messages, status, error, loadMessages, sendMessage, retryLastMessage } = useChat()
  const [draft, setDraft] = useState("")
  const bottomRef = useRef(null)
  const location = useLocation()

  // Opened from a task ("Talk to Mentra" on a TaskCard) or from a plan
  // adjustment's "Request changes" — carries that context as router state
  // (Phase 2 §C.8: "if opened from a task, a small 'About: [task title]'
  // chip above the input"). Falls back to no context for the normal nav
  // entry point.
  const [context, setContext] = useState(() =>
    location.state?.taskId ? { taskId: location.state.taskId, label: location.state.taskTitle } : null
  )
  useEffect(() => {
    if (location.state?.taskId) {
      setContext({ taskId: location.state.taskId, label: location.state.taskTitle })
    } else if (location.state?.adjustmentSummary) {
      setContext({ taskId: null, label: location.state.adjustmentSummary, isAdjustment: true })
    }
  }, [location.state])

  useEffect(() => { loadMessages() }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, status])

  function handleSend(text) {
    const value = (text ?? draft).trim()
    if (!value) return
    setDraft("")
    sendMessage(value, context?.taskId ?? undefined)
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col md:h-[calc(100vh-5rem)]">
      <h1 className="font-serif text-2xl text-ink">Talk to Mentra</h1>

      {context && (
        <div className="mt-2 flex w-fit items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
          <span>About: {context.label}</span>
          <button
            type="button"
            onClick={() => setContext(null)}
            aria-label="Clear task context"
            className="text-muted hover:text-ink"
          >
          </button>
        </div>
      )}

      <div className="mt-4 flex-1 space-y-4 overflow-y-auto pr-1">
        {status === "loading" && messages.length === 0 && <TypingIndicator />}

        {status === "error" && messages.length === 0 && <ErrorState message={error} onRetry={loadMessages} />}

        {messages.length === 0 && status === "success" && (
          <EmptyState title="Tell me how today's going" description="Progress, doubts, schedule changes —  just say it naturally." />
        )}

        {messages.map((m) => <ChatBubble key={m.id} message={m} />)}
        {status === "sending" && <TypingIndicator />}
        {status === "error" && messages.length > 0 && <ErrorState message={error} onRetry={retryLastMessage} />}
        <div ref={bottomRef} />
      </div>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {SUGGESTIONS.map((s) => <SuggestionChip key={s} onClick={() => handleSend(s)}>{s}</SuggestionChip>)}
      </div>

      <form
        className="mt-3 flex items-center gap-2 border-t border-line pt-3"
        onSubmit={(e) => { e.preventDefault(); handleSend() }}
      >
        <input
          className="flex-1 rounded-lg border border-line px-3.5 py-2.5 text-sm focus:border-primary focus:outline-none"
          placeholder="Type a message…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit" className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50" disabled={status === "sending"}>
          Send
        </button>
      </form>
    </div>
  )
}
