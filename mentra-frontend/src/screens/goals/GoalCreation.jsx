import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Button, TextField, TextArea, DatePicker, ErrorState } from "../../components/ui.jsx"

export default function GoalCreation() {
  const { createGoal, goal } = useMentraData()
  const navigate = useNavigate()
  const [form, setForm] = useState({ title: "", target_outcome: "", current_level: "", target_date: "" })
  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      const created = await createGoal(form)
      navigate(`/goals/${created.id}/assessment`)
    } catch { /* error rendered below via goal.status */ }
  }

  return (
    <div>
      <h1 className="font-serif text-2xl text-ink">What are you working toward?</h1>
      <p className="mt-1 text-sm text-muted">Mentra will use this to build your assessment and roadmap.</p>

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <TextField label="Goal" placeholder="e.g. Learn DSA for placement interviews" value={form.title} onChange={(e) => update("title", e.target.value)} required />
        <TextArea label="What does success look like?" value={form.target_outcome} onChange={(e) => update("target_outcome", e.target.value)} required />
        <TextArea label="Where are you starting from?" value={form.current_level} onChange={(e) => update("current_level", e.target.value)} required />
        <DatePicker label="Target date" value={form.target_date} onChange={(e) => update("target_date", e.target.value)} required />
        {goal.status === "error" && <ErrorState message={goal.error} onRetry={handleSubmit} />}
        <Button type="submit" loading={goal.status === "loading"}>Continue</Button>
      </form>
    </div>
  )
}
