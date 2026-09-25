import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMentraData } from "../../state/MentraDataContext.jsx"
import { Button, TextField, TextArea, Chip, ErrorState, Spinner } from "../../components/ui.jsx"

const STEPS = ["Routine", "Time & schedule", "Knowledge & constraints", "Preferences"]
const CONSTRAINT_OPTIONS = ["College classes", "Working full-time", "Exams coming up", "Limited weekday time"]
const PREFERENCE_OPTIONS = ["Short daily sessions", "Longer weekend sessions", "Visual explanations", "Practice-heavy"]

export default function Onboarding() {
  const { completeOnboarding } = useMentraData()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [form, setForm] = useState({
    daily_routine: "",
    available_time: "",
    preferred_schedule: "",
    existing_knowledge: "",
    constraints: [],
    preferences: [],
  })

  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }))
  const toggleMulti = (key, value) =>
    setForm((f) => ({ ...f, [key]: f[key].includes(value) ? f[key].filter((v) => v !== value) : [...f[key], value] }))

  async function handleNext() {
    if (step < STEPS.length - 1) { setStep(step + 1); return }
    setSubmitting(true); setError(null)
    try {
      await completeOnboarding(form)
      navigate("/goals/new")
    } catch {
      setError("Couldn't save your details — check your connection and try again.")
    } finally {
      setSubmitting(false)
    }
  }

  if (submitting) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted">Setting things up</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-content px-4 py-10">
      <div className="mb-6 h-1.5 w-full overflow-hidden rounded-full bg-line/60">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>
      <h1 className="font-serif text-2xl text-ink">{STEPS[step]}</h1>

      <div className="mt-6 space-y-5">
        {step === 0 && (
          <TextArea
            label="Tell me about a typical day classes, work, other commitments"
            value={form.daily_routine}
            onChange={(e) => update("daily_routine", e.target.value)}
          />
        )}
        {step === 1 && (
          <>
            <TextField label="How much time can you realistically give most days?" placeholder="e.g. 45 minutes" value={form.available_time} onChange={(e) => update("available_time", e.target.value)} />
            <TextField label="Any preferred time of day?" placeholder="e.g. evenings after 7pm" value={form.preferred_schedule} onChange={(e) => update("preferred_schedule", e.target.value)} />
          </>
        )}
        {step === 2 && (
          <>
            <TextArea label="What do you already know or have experience with?" value={form.existing_knowledge} onChange={(e) => update("existing_knowledge", e.target.value)} />
            <div>
              <span className="mb-1.5 block text-sm font-medium text-ink">Anything that limits your time right now?</span>
              <div className="flex flex-wrap gap-2">
                {CONSTRAINT_OPTIONS.map((o) => (
                  <Chip key={o} selected={form.constraints.includes(o)} onClick={() => toggleMulti("constraints", o)}>{o}</Chip>
                ))}
              </div>
            </div>
          </>
        )}
        {step === 3 && (
          <div>
            <span className="mb-1.5 block text-sm font-medium text-ink">How do you like to learn?</span>
            <div className="flex flex-wrap gap-2">
              {PREFERENCE_OPTIONS.map((o) => (
                <Chip key={o} selected={form.preferences.includes(o)} onClick={() => toggleMulti("preferences", o)}>{o}</Chip>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && <div className="mt-4"><ErrorState message={error} onRetry={handleNext} /></div>}

      <div className="mt-8 flex justify-between">
        <Button variant="secondary" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>Back</Button>
        <Button onClick={handleNext}>{step === STEPS.length - 1 ? "Continue" : "Next"}</Button>
      </div>
    </div>
  )
}
