import { useEffect, useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Card, Skeleton, ErrorState, ProgressBar } from "../../components/ui.jsx"
import { AdjustmentBanner } from "../../components/domain.jsx"

const PERIODS = ["daily", "weekly", "monthly"]

export default function Dashboard() {
  const { progress, loadProgress, adjustments, loadAdjustments } = useMentraData()
  const [period, setPeriod] = useState("weekly")
  const navigate = useNavigate()

  useEffect(() => { loadProgress(period) }, [period])
  useEffect(() => { loadAdjustments() }, [])

  const pending = adjustments.data?.[0]
  const data = progress.data

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-2xl text-ink">Your progress</h1>
        <div className="flex rounded-lg border border-line p-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize ${period === p ? "bg-primary text-white" : "text-muted"}`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {pending && <div className="mt-5"><AdjustmentBanner onOpen={() => navigate(`/adjustments/${pending.id}`)} /></div>}

      {progress.status === "loading" && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      )}

      {progress.status === "error" && <div className="mt-6"><ErrorState message={progress.error} onRetry={() => loadProgress(period)} /></div>}

      {progress.status === "success" && data && (
        <>
          {data.weekly?.tasks_completed === 0 ? (
            <Card className="mt-6">
              <p className="text-sm text-muted">Your progress will show up here once you complete a few tasks.</p>
            </Card>
          ) : (
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Card>
                <p className="text-xs font-medium text-muted">This {period.replace("ly", "")}</p>
                <p className="mt-1 text-2xl font-semibold text-ink">
                  {data[period]?.tasks_completed ?? "\u2014"} <span className="text-sm font-normal text-muted">completed</span>
                </p>
                <p className="text-sm text-muted">{data[period]?.tasks_missed ?? 0} missed</p>
              </Card>
              <Card>
                <p className="text-xs font-medium text-muted">Consistency</p>
                <p className="mt-1 text-2xl font-semibold text-ink">{data[period]?.consistency_pct ?? "\u2014"}%</p>
                {data.weekly?.streak_days != null && <p className="text-sm text-muted">{data.weekly.streak_days}-day streak</p>}
              </Card>
              <Card>
                <p className="text-xs font-medium text-muted">Goal progress</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{data.weekly?.goal_progress_pct ?? 0}%</p>
                <div className="mt-2"><ProgressBar value={data.weekly?.goal_progress_pct ?? 0} /></div>
              </Card>
              <Card>
                <p className="text-xs font-medium text-muted">Trend</p>
                <p className="mt-1 text-sm text-ink">{data.weekly?.trend}</p>
              </Card>
            </div>
          )}

          {data.upcoming?.length > 0 && (
            <div className="mt-8">
              <p className="text-sm font-medium text-ink">Upcoming</p>
              <ul className="mt-2 space-y-2">
                {data.upcoming.map((t) => (
                  <li key={t.id}>
                    <Link to="/tasks" className="text-sm text-primary">{t.title}</Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}
