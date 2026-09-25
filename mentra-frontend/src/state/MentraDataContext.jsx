import { createContext, useCallback, useContext, useState } from "react"
import { goalsApi, roadmapApi, tasksApi, progressApi, adjustmentsApi, notificationsApi, profileApi } from "../api/index.js"

const MentraDataContext = createContext(null)

// Each resource tracks its own { status, data, error } so screens can render
// Loading/Empty/Error/Success independently — see plan §I.
function initResource() {
  return { status: "idle", data: null, error: null }
}

export function MentraDataProvider({ children }) {
  const [goal, setGoal] = useState(initResource())
  const [assessment, setAssessment] = useState(initResource())
  const [roadmap, setRoadmap] = useState(initResource())
  const [tasksToday, setTasksToday] = useState(initResource())
  const [tasksWeek, setTasksWeek] = useState(initResource())
  const [progress, setProgress] = useState(initResource())
  const [adjustments, setAdjustments] = useState(initResource())
  const [notifications, setNotifications] = useState(initResource())

  const run = async (setter, fn) => {
    setter((s) => ({ ...s, status: "loading", error: null }))
    try {
      const data = await fn()
      setter({ status: "success", data, error: null })
      return data
    } catch (e) {
      setter((s) => ({ ...s, status: "error", error: "Something went wrong loading this. " }))
      throw e
    }
  }

  const completeOnboarding = useCallback((payload) => profileApi.completeOnboarding(payload), [])

  const createGoal = useCallback((payload) => run(setGoal, () => goalsApi.create(payload)), [])
  const loadAssessment = useCallback((goalId) => run(setAssessment, () => goalsApi.getAssessment(goalId)), [])
  const loadRoadmap = useCallback((goalId) => run(setRoadmap, () => roadmapApi.get(goalId)), [])
  const editMilestone = useCallback((id, payload) => roadmapApi.updateMilestone(id, payload), [])

  const loadTasksToday = useCallback(() => run(setTasksToday, () => tasksApi.listToday()), [])
  const loadTasksWeek = useCallback(() => run(setTasksWeek, () => tasksApi.listWeek()), [])
  const setTaskStatus = useCallback(async (taskId, status) => {
    await tasksApi.updateStatus(taskId, status)
    setTasksToday((s) => ({ ...s, data: (s.data || []).map((t) => (t.id === taskId ? { ...t, status } : t)) }))
    setTasksWeek((s) => ({ ...s, data: (s.data || []).map((t) => (t.id === taskId ? { ...t, status } : t)) }))
  }, [])
  const patchTaskFromChat = useCallback((taskId, status) => {
    setTasksToday((s) => ({ ...s, data: (s.data || []).map((t) => (t.id === taskId ? { ...t, status } : t)) }))
    setTasksWeek((s) => ({ ...s, data: (s.data || []).map((t) => (t.id === taskId ? { ...t, status } : t)) }))
  }, [])

  const loadProgress = useCallback((period) => run(setProgress, () => progressApi.summary(period)), [])

  const loadAdjustments = useCallback(() => run(setAdjustments, () => adjustmentsApi.listProposed()), [])
  const respondToAdjustment = useCallback(async (id, action) => {
    await adjustmentsApi.respond(id, action)
    // Only an accepted adjustment actually changes the roadmap/tasks (see
    // adaptation/router.py::respond_adjustment) — decline/request_changes
    // leave the plan untouched, so refetching for those is just wasted
    // network calls.
    if (action === "accept") {
      await Promise.all([loadRoadmap(goal.data?.id || "current"), loadTasksToday(), loadTasksWeek()])
    }
  }, [goal.data, loadRoadmap, loadTasksToday, loadTasksWeek])

  const loadNotifications = useCallback(() => run(setNotifications, () => notificationsApi.list()), [])
  const markNotificationRead = useCallback(async (id) => {
    await notificationsApi.markRead(id)
    setNotifications((s) => ({ ...s, data: (s.data || []).map((n) => (n.id === id ? { ...n, is_read: true } : n)) }))
  }, [])

  return (
    <MentraDataContext.Provider
      value={{
        goal, assessment, roadmap, tasksToday, tasksWeek, progress, adjustments, notifications,
        completeOnboarding, createGoal, loadAssessment, loadRoadmap, editMilestone,
        loadTasksToday, loadTasksWeek, setTaskStatus, patchTaskFromChat,
        loadProgress, loadAdjustments, respondToAdjustment,
        loadNotifications, markNotificationRead,
      }}
    >
      {children}
    </MentraDataContext.Provider>
  )
}

export function useMentraData() {
  return useContext(MentraDataContext)
}
