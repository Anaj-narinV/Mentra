import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Button, Skeleton, ErrorState } from "../../components/ui.jsx"
import { MentorMessageBlock } from "../../components/domain.jsx"

export default function AssessmentResult() {
  const { goalId } = useParams()
  const { assessment, loadAssessment, loadRoadmap } = useMentraData()
  const navigate = useNavigate()

  useEffect(() => { loadAssessment(goalId) }, [goalId])

  async function handleContinue() {
    await loadRoadmap(goalId)
    navigate("/roadmap")
  }

  return (
    <div>
      <h1 className="font-serif text-2xl text-ink">Here's how I see it</h1>

      {assessment.status === "loading" && (
        <div className="mt-6 space-y-3">
          <p className="text-sm text-muted">Mentra is thinking about your goal</p>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}

      {assessment.status === "error" && (
        <div className="mt-6"><ErrorState message={assessment.error} onRetry={() => loadAssessment(goalId)} /></div>
      )}

      {assessment.status === "success" && assessment.data && (
        <div className="mt-6 space-y-6">
          <MentorMessageBlock>{assessment.data.ai_summary}</MentorMessageBlock>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium text-muted">Difficulty</dt>
              <dd className="mt-0.5 text-sm text-ink">{assessment.data.difficulty_level}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted">Recommended workload</dt>
              <dd className="mt-0.5 text-sm text-ink">{assessment.data.recommended_workload}</dd>
            </div>
          </dl>
          <Button onClick={handleContinue}>Continue to roadmap</Button>
        </div>
      )}
    </div>
  )
}
