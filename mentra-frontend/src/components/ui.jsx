// Shared UI primitives. Kept in one file deliberately — this is the whole
// reusable component kit for a small MVP surface; split into separate files
// per component if/when the kit grows past this size.

export function Button({ children, variant = "primary", loading, className = "", ...props }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
  const variants = {
    primary: "bg-primary text-white hover:bg-primary-light",
    secondary: "bg-surface text-ink border border-line hover:border-primary",
    ghost: "text-primary hover:bg-primary/5",
    danger: "bg-surface text-danger border border-danger/30 hover:bg-danger/5",
  }
  return (
    <button className={`${base} ${variants[variant]} ${className}`} disabled={loading || props.disabled} {...props}>
      {loading && <Spinner small />}
      {children}
    </button>
  )
}

export function Spinner({ small }) {
  const size = small ? "h-4 w-4" : "h-6 w-6"
  return (
    <svg className={`${size} animate-spin text-current`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}

export function TextField({ label, error, className = "", ...props }) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>}
      <input
        className={`w-full rounded-lg border px-3.5 py-2.5 text-sm text-ink placeholder:text-muted focus:border-primary focus:outline-none ${error ? "border-danger" : "border-line"} ${className}`}
        {...props}
      />
      {error && <span className="mt-1 block text-sm text-danger">{error}</span>}
    </label>
  )
}

export function TextArea({ label, error, className = "", ...props }) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>}
      <textarea
        className={`w-full rounded-lg border px-3.5 py-2.5 text-sm text-ink placeholder:text-muted focus:border-primary focus:outline-none ${error ? "border-danger" : "border-line"} ${className}`}
        rows={3}
        {...props}
      />
      {error && <span className="mt-1 block text-sm text-danger">{error}</span>}
    </label>
  )
}

export function DatePicker({ label, ...props }) {
  return <TextField type="date" label={label} {...props} />
}

export function Chip({ selected, children, ...props }) {
  return (
    <button
      type="button"
      className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
        selected ? "border-primary bg-primary text-white" : "border-line text-ink hover:border-primary"
      }`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Card({ children, className = "" }) {
  return <div className={`rounded-xl border border-line bg-surface p-5 ${className}`}>{children}</div>
}

export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-md bg-line/60 ${className}`} />
}

export function EmptyState({ title, description }) {
  return (
    <div className="rounded-xl border border-dashed border-line px-6 py-10 text-center">
      <p className="font-medium text-ink">{title}</p>
      {description && <p className="mt-1 text-sm text-muted">{description}</p>}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-danger/30 bg-danger/5 px-4 py-3">
      <p className="text-sm text-danger">{message || "Something went wrong."}</p>
      {onRetry && (
        <button onClick={onRetry} className="text-sm font-medium text-danger underline underline-offset-2">
          Retry
        </button>
      )}
    </div>
  )
}

const STATUS_STYLES = {
  pending: "bg-line/60 text-ink",
  completed: "bg-success/15 text-success",
  partially_completed: "bg-warning/15 text-warning",
  skipped: "bg-muted/15 text-muted",
  rescheduled: "bg-accent/15 text-accent",
}
const STATUS_LABELS = {
  pending: "Pending",
  completed: "Completed",
  partially_completed: "Partially done",
  skipped: "Skipped",
  rescheduled: "Rescheduled",
}
export function StatusBadge({ status }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[status] || STATUS_STYLES.pending}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export function ProgressBar({ value }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-line/60">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  )
}
