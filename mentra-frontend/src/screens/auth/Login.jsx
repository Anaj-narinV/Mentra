import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../../state/AuthContext.jsx"
import { profileApi } from "../../api/index.js"
import { Button, TextField, Card, ErrorState } from "../../components/ui.jsx"

export default function Login() {
  const { login, status, error } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      await login(email, password)
      // A user who never finished onboarding (closed the tab mid-flow, etc.)
      // should land back in onboarding, not on an empty Dashboard — reuses
      // the existing Profile.onboarding_complete flag (Signup already routes
      // new accounts straight to /onboarding; this covers returning-but-
      // incomplete accounts the same way). If the profile check itself fails
      // for any reason, fail open to /dashboard rather than blocking login.
      try {
        const profile = await profileApi.get()
        navigate(profile.onboarding_complete ? "/dashboard" : "/onboarding")
      } catch {
        navigate("/dashboard")
      }
    } catch { /* error shown via context */ }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <Card className="w-full max-w-sm">
        <h1 className="font-serif text-2xl text-primary">Mentra</h1>
        <p className="mt-1 text-sm text-muted">Welcome back — let's see where you left off.</p>
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          {error && <ErrorState message={error} />}
          <Button type="submit" className="w-full" loading={status === "loading"}>Log in</Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted">
          New here? <Link to="/signup" className="font-medium text-primary">Create an account</Link>
        </p>
      </Card>
    </div>
  )
}
