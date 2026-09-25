import { useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Skeleton, ErrorState, EmptyState } from "../../components/ui.jsx"
import { NotificationItem } from "../../components/domain.jsx"

export default function Notifications() {
  const { notifications, loadNotifications, markNotificationRead } = useMentraData()
  const navigate = useNavigate()

  useEffect(() => { loadNotifications() }, [])

  function handleOpen(n) {
    markNotificationRead(n.id)
    if (n.type === "adjustment" && n.related_adjustment_id) navigate(`/adjustments/${n.related_adjustment_id}`)
    else if (n.type === "adjustment") navigate("/dashboard")
    else if (n.related_task_id) navigate("/tasks")
    else navigate("/roadmap")
  }

  return (
    <div>
      <h1 className="font-serif text-2xl text-ink">Notifications</h1>

      <div className="mt-6">
        {notifications.status === "loading" && (
          <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        )}
        {notifications.status === "error" && <ErrorState message={notifications.error} onRetry={loadNotifications} />}
        {notifications.status === "success" && notifications.data.length === 0 && (
          <EmptyState title="Nothing new" description="You\u2019re all caught up." />
        )}
        {notifications.status === "success" &&
          notifications.data.map((n) => <NotificationItem key={n.id} notification={n} onOpen={handleOpen} />)}
      </div>
    </div>
  )
}
