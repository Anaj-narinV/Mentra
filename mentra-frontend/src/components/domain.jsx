// Domain components shared across screens. The mentor voice — assessment
// text, chat replies, adjustment proposals — is always set in font-serif
// with an accent rule, per the design plan; everything else stays font-sans.
import { Link } from "react-router-dom"
import { Card, StatusBadge, ProgressBar, Button } from "./ui.jsx"

export function MentorMessageBlock({ children, className = "" }) {
  return (
    <div className={`border-l-2 border-accent bg-accent/5 py-3 pl-4 pr-3 ${className}`}>
      <p className="font-serif text-[17px] leading-relaxed text-ink">{children}</p>
    </div>
  )
}

export function MilestoneItem({ milestone, expanded, onToggle }) {
  const statusLabel = { in_progress: "In progress", upcoming: "Upcoming", completed: "Complete" }[milestone.status]
  const isDone = milestone.status === "completed"
  const isActive = milestone.status === "in_progress"
  return (
    <li className="relative pl-8">
      <span
        className={`absolute left-0 top-1.5 h-3 w-3 rounded-full border-2 ${
          isActive
            ? "border-primary bg-primary"
            : isDone
              ? "border-success bg-success"
              : "border-line bg-surface"
        }`}
      />
      <button onClick={onToggle} className="w-full text-left">
        <div className="flex items-center justify-between gap-3">
          <span className={`font-medium ${isActive || isDone ? "text-ink" : "text-muted"} ${isDone ? "line-through decoration-success/60" : ""}`}>
            {milestone.title}
          </span>
          <span className="shrink-0 text-xs text-muted">{milestone.target_date}</span>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <div className="w-32"><ProgressBar value={milestone.progress_pct} /></div>
          <span className={`text-xs ${isDone ? "text-success" : "text-muted"}`}>{statusLabel}</span>
        </div>
      </button>
      {expanded && (
        <ul className="mt-2 space-y-1 border-l border-line pl-3 text-sm text-muted">
          {milestone.tasks_preview.map((t) => <li key={t}>{t}</li>)}
        </ul>
      )}
    </li>
  )
}

export function MilestoneTimeline({ milestones, expandedId, onToggle }) {
  return (
    <ul className="space-y-5">
      {milestones.map((m) => (
        <MilestoneItem key={m.id} milestone={m} expanded={expandedId === m.id} onToggle={() => onToggle(m.id)} />
      ))}
    </ul>
  )
}

export function TaskCard({ task, onStatusChange }) {
  return (
    <Card className="space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-ink">{task.title}</p>
          <p className="mt-0.5 text-sm text-muted">{task.description}</p>
        </div>
        <StatusBadge status={task.status} />
      </div>
      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-muted">{task.estimated_duration} · {task.priority} priority</span>
        <div className="flex items-center gap-3">
          <Link
            to="/chat"
            state={{ taskId: task.id, taskTitle: task.title }}
            className="text-xs font-medium text-primary"
          >
            Talk to Mentra
          </Link>
          {task.status === "pending" && (
            <>
              <button className="text-xs font-medium text-success" onClick={() => onStatusChange(task.id, "completed")}>Complete</button>
              <button className="text-xs font-medium text-muted" onClick={() => onStatusChange(task.id, "skipped")}>Skip</button>
            </>
          )}
        </div>
      </div>
    </Card>
  )
}

export function AdjustmentBanner({ onOpen }) {
  return (
    <button
      onClick={onOpen}
      className="mb-5 flex w-full items-center justify-between rounded-lg border border-accent/40 bg-accent/10 px-4 py-3 text-left"
    >
      <span className="text-sm font-medium text-ink">Mentra has a plan adjustment for you to review</span>
      <span className="text-sm font-medium text-accent">Review \u2192</span>
    </button>
  )
}

export function AdjustmentProposalCard({ adjustment, onRespond, onRequestChanges, responding }) {
  return (
    <div className="rounded-xl border-2 border-accent bg-accent/5 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-accent">Plan adjustment</p>
      <MentorMessageBlock className="mt-2 border-l-0 bg-transparent pl-0">{adjustment.change_summary}</MentorMessageBlock>
      <p className="mt-3 text-sm text-muted">{adjustment.trigger_reason}</p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium text-muted">Current plan</p>
          <ul className="mt-1.5 space-y-1 text-sm text-ink">
            {adjustment.current_plan.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
        <div>
          <p className="text-xs font-medium text-muted">Proposed plan</p>
          <ul className="mt-1.5 space-y-1 text-sm text-ink">
            {adjustment.proposed_plan.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      </div>

      <p className="mt-4 text-sm text-muted"><span className="font-medium text-ink">Expected effect: </span>{adjustment.expected_effect}</p>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button loading={responding === "accept"} onClick={() => onRespond("accept")}>Accept</Button>
        <Button variant="secondary" loading={responding === "decline"} onClick={() => onRespond("decline")}>Decline</Button>
        <Button variant="ghost" loading={responding === "request_changes"} onClick={onRequestChanges}>Request changes</Button>
      </div>
    </div>
  )
}

export function NotificationItem({ notification, onOpen }) {
  return (
    <button onClick={() => onOpen(notification)} className="flex w-full items-start gap-3 border-b border-line py-3.5 text-left last:border-0">
      {!notification.is_read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" />}
      {notification.is_read && <span className="mt-1.5 h-2 w-2 shrink-0" />}
      <div>
        <p className={`text-sm ${notification.is_read ? "text-muted" : "text-ink font-medium"}`}>{notification.message}</p>
      </div>
    </button>
  )
}
