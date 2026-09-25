import { Routes, Route, Navigate } from "react-router-dom"
import ProtectedRoute from "./components/ProtectedRoute.jsx"
import AppShell from "./components/AppShell.jsx"

import Login from "./screens/auth/Login.jsx"
import Signup from "./screens/auth/Signup.jsx"
import Onboarding from "./screens/onboarding/Onboarding.jsx"
import GoalCreation from "./screens/goals/GoalCreation.jsx"
import AssessmentResult from "./screens/assessment/AssessmentResult.jsx"
import Roadmap from "./screens/roadmap/Roadmap.jsx"
import Tasks from "./screens/tasks/Tasks.jsx"
import Chat from "./screens/chat/Chat.jsx"
import Dashboard from "./screens/dashboard/Dashboard.jsx"
import PlanAdjustment from "./screens/adjustment/PlanAdjustment.jsx"
import Notifications from "./screens/notifications/Notifications.jsx"

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
      <Route path="/goals/new" element={<ProtectedRoute><GoalCreation /></ProtectedRoute>} />
      <Route path="/goals/:goalId/assessment" element={<ProtectedRoute><AssessmentResult /></ProtectedRoute>} />

      <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/roadmap" element={<Roadmap />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/adjustments/:id" element={<PlanAdjustment />} />
        <Route path="/notifications" element={<Notifications />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
