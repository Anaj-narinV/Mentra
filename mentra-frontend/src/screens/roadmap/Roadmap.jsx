import { useEffect, useState } from "react"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Skeleton, ErrorState, EmptyState } from "../../components/ui.jsx"
import { MilestoneTimeline, AdjustmentBanner } from "../../components/domain.jsx"
import { useNavigate } from "react-router-dom"

// "current" is resolved server-side to the user's single active goal
// (MVP: one goal per user) — see backend/app/core/resolvers.py.
const GOAL_ID = "current"

export default function Roadmap() {
  const { roadmap, loadRoadmap, adjustments, loadAdjustments } = useMentraData()
  const [expandedId, setExpandedId] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    loadRoadmap(GOAL_ID)
    loadAdjustments()
  }, [])

  const pending = adjustments.data?.[0]

  return (
    <div>
      <h1 className="font-serif text-2xl text-ink">Your roadmap</h1>

      {pending && <div className="mt-5"><AdjustmentBanner onOpen={() => navigate(`/adjustments/${pending.id}`)} /></div>}

      {roadmap.status === "loading" && (
        <div className="mt-6 space-y-5">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      )}

      {roadmap.status === "error" && <div className="mt-6"><ErrorState message={roadmap.error} onRetry={() => loadRoadmap(GOAL_ID)} /></div>}

      {roadmap.status === "success" && roadmap.data && roadmap.data.milestones.length > 0 && (
        <div className="mt-8">
          <MilestoneTimeline milestones={roadmap.data.milestones} expandedId={expandedId} onToggle={(id) => setExpandedId((cur) => (cur === id ? null : id))} />
        </div>
      )}

      {roadmap.status === "success" && roadmap.data?.milestones.length === 0 && (
        <div className="mt-6"><EmptyState title="No roadmap yet" description="Create a goal to generate one." /></div>
      )}
    </div>
  )
}
