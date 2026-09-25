import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { adjustmentsApi } from "../../api/index.js"
import { Skeleton, ErrorState, Button } from "../../components/ui.jsx"
import { AdjustmentProposalCard } from "../../components/domain.jsx"

export default function PlanAdjustment() {
  const { id } = useParams()
  const { respondToAdjustment } = useMentraData()
  const navigate = useNavigate()
  const [state, setState] = useState({ status: "loading", data: null, error: null })
  const [responding, setResponding] = useState(null)
  const [doneAction, setDoneAction] = useState(null) // "accept" | "decline" | null

  async function load() {
    setState({ status: "loading", data: null, error: null })
    try {
      const data = await adjustmentsApi.get(id)
      setState({ status: "success", data, error: null })
    } catch (e) {
      if (e?.status === 404) {
        // Phase 2 §C.10: a direct nav to a nonexistent adjustment redirects
        // to Dashboard rather than showing a dead-end error+retry loop.
        navigate("/dashboard", { replace: true })
        return
      }
      setState({ status: "error", data: null, error: "Couldn't load this adjustment." })
    }
  }
  useEffect(() => { load() }, [id])

  async function handleRespond(action) {
    setResponding(action)
    try {
      await respondToAdjustment(id, action)
      setDoneAction(action)
      setTimeout(() => navigate("/dashboard"), 1200)
    } catch {
      setState((s) => ({ ...s, error: "That didn't go through try again." }))
    } finally {
      setResponding(null)
    }
  }

  async function handleRequestChanges() {
    setResponding("request_changes")
    try {
      await respondToAdjustment(id, "request_changes")
      navigate("/chat", { state: { adjustmentSummary: state.data?.change_summary } })
    } catch {
      setState((s) => ({ ...s, error: "That didn't go through try again." }))
      setResponding(null)
    }
  }

  return (
    <div>
      <h1 className="font-serif text-2xl text-ink">Plan adjustment</h1>

      {state.status === "loading" && <div className="mt-6"><Skeleton className="h-56 w-full" /></div>}
      {state.status === "error" && <div className="mt-6"><ErrorState message={state.error} onRetry={load} /></div>}

      {doneAction === "accept" && <p className="mt-6 text-sm text-success">Got it \u2014 your plan is updated.</p>}
      {doneAction === "decline" && <p className="mt-6 text-sm text-muted">Got it \u2014 no changes made, your plan stays as it was.</p>}

      {!doneAction && state.status === "success" && state.data && (
        <div className="mt-6">
          <AdjustmentProposalCard
            adjustment={state.data}
            onRespond={handleRespond}
            onRequestChanges={handleRequestChanges}
            responding={responding}
          />
        </div>
      )}
    </div>
  )
}
