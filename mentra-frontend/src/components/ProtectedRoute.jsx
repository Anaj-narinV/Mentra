import { Navigate } from "react-router-dom"
import { useAuth } from "../state/AuthContext.jsx"
import { Spinner } from "./ui.jsx"

export default function ProtectedRoute({ children }) {
  const { user, ready } = useAuth()
  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}
