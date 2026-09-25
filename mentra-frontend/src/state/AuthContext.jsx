import { createContext, useContext, useEffect, useState } from "react"
import { authApi } from "../api/index.js"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState("idle") // idle | loading | error
  const [error, setError] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem("mentra_token")
    const savedUser = localStorage.getItem("mentra_user")
    if (token && savedUser) setUser(JSON.parse(savedUser))
    setReady(true)
  }, [])

  async function login(email, password) {
    setStatus("loading"); setError(null)
    try {
      const { token, user: u } = await authApi.login(email, password)
      localStorage.setItem("mentra_token", token)
      localStorage.setItem("mentra_user", JSON.stringify(u))
      setUser(u); setStatus("success")
      return u
    } catch (e) {
      setStatus("error"); setError("That email/password doesn\u2019t match — try again.")
      throw e
    }
  }

  async function signup(name, email, password) {
    setStatus("loading"); setError(null)
    try {
      const { token, user: u } = await authApi.signup(name, email, password)
      localStorage.setItem("mentra_token", token)
      localStorage.setItem("mentra_user", JSON.stringify(u))
      setUser(u); setStatus("success")
      return u
    } catch (e) {
      setStatus("error"); setError("We couldn\u2019t create your account — try again.")
      throw e
    }
  }

  function logout() {
    localStorage.removeItem("mentra_token")
    localStorage.removeItem("mentra_user")
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, status, error, ready, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
