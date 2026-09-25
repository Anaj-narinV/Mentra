export function ChatBubble({ message }) {
  const isAi = message.sender === "ai"
  return (
    <div className={`flex ${isAi ? "justify-start" : "justify-end"}`}>
      <div
        className={
          isAi
            ? "max-w-[85%] border-l-2 border-accent bg-accent/5 px-4 py-3"
            : "max-w-[85%] rounded-xl bg-primary px-4 py-2.5 text-white"
        }
      >
        <p className={isAi ? "font-serif text-[16px] leading-relaxed text-ink" : "text-sm"}>{message.content}</p>
      </div>
    </div>
  )
}

export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1 border-l-2 border-accent bg-accent/5 px-4 py-3">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.2s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.1s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent" />
      </div>
    </div>
  )
}

export function SuggestionChip({ children, onClick }) {
  return (
    <button onClick={onClick} className="shrink-0 rounded-full border border-line px-3 py-1.5 text-sm text-ink hover:border-primary">
      {children}
    </button>
  )
}
