import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Skeleton, ErrorState, EmptyState } from "../../components/ui.jsx"
import { TaskCard, AdjustmentBanner } from "../../components/domain.jsx"

export default function Tasks() {
  const { tasksToday, tasksWeek, loadTasksToday, loadTasksWeek, setTaskStatus, adjustments, loadAdjustments } = useMentraData()
  const [view, setView] = useState("today")
  const navigate = useNavigate()

  useEffect(() => {
    loadTasksToday()
    loadTasksWeek()
    loadAdjustments()
  }, [])

  const resource = view === "today" ? tasksToday : tasksWeek
  const pending = adjustments.data?.[0]

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-2xl text-ink">Tasks</h1>
        <div className="flex rounded-lg border border-line p-1">
          {["today", "week"].map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize ${view === v ? "bg-primary text-white" : "text-muted"}`}
            >
              {v === "today" ? "Today" : "This week"}
            </button>
          ))}
        </div>
      </div>

      {pending && <div className="mt-5"><AdjustmentBanner onOpen={() => navigate(`/adjustments/${pending.id}`)} /></div>}

      <div className="mt-6 space-y-3">
        {resource.status === "loading" && [1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}
        {resource.status === "error" && (
          <ErrorState message={resource.error} onRetry={() => (view === "today" ? loadTasksToday() : loadTasksWeek())} />
        )}
        {resource.status === "success" && resource.data.length === 0 && (
          <EmptyState title="Nothing scheduled" description="Enjoy the break." />
        )}
        {resource.status === "success" &&
          resource.data.map((task) => <TaskCard key={task.id} task={task} onStatusChange={setTaskStatus} />)}
      </div>
    </div>
  )
}
