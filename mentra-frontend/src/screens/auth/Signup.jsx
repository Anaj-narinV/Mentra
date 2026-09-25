import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../../state/AuthContext.jsx"
import { Button, TextField, Card, ErrorState } from "../../components/ui.jsx"

export default function Signup() {
  const { signup, status, error } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      await signup(name, email, password)
      navigate("/onboarding")
    } catch { /* error shown via context */ }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <Card className="w-full max-w-sm">
        <h1 className="font-serif text-2xl text-primary">Mentra</h1>
        <p className="mt-1 text-sm text-muted">Let's set up your mentor.</p>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          {error && <ErrorState message={error} />}
          <Button type="submit" className="w-full" loading={status === "loading"}>Create account</Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted">
          Already have an account? <Link to="/login" className="font-medium text-primary">Log in</Link>
        </p>
      </Card>
    </div>
  )
}
