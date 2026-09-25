// Grouped endpoint functions — one group per backend module (matches the
// Architecture doc §9). Every screen imports from here, never from client.js
// or mocks/ directly.
import { request } from "./client.js"

export const authApi = {
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  signup: (name, email, password) => request("/auth/signup", { method: "POST", body: { name, email, password } }),
}

export const profileApi = {
  get: () => request("/profile"),
  update: (payload) => request("/profile", { method: "PUT", body: payload }),
  completeOnboarding: (payload) => request("/onboarding", { method: "POST", body: payload }),
}

export const goalsApi = {
  create: (payload) => request("/goals", { method: "POST", body: payload }),
  getAssessment: (goalId) => request(`/goals/${goalId}/assessment`),
}

export const roadmapApi = {
  get: (goalId) => request(`/goals/${goalId}/roadmap`),
  updateMilestone: (milestoneId, payload) => request(`/milestones/${milestoneId}`, { method: "PUT", body: payload }),
}

export const tasksApi = {
  listToday: () => request("/tasks?date=today"),
  listWeek: () => request("/tasks?range=week"),
  updateStatus: (taskId, status) => request(`/tasks/${taskId}/status`, { method: "PUT", body: { status } }),
}

export const conversationApi = {
  getMessages: (conversationId) => request(`/conversations/${conversationId}/messages`),
  sendMessage: (conversationId, content, taskId) =>
    request(`/conversations/${conversationId}/messages`, { method: "POST", body: { content, task_id: taskId ?? null } }),
}

export const progressApi = {
  summary: (period = "weekly") => request(`/progress/summary?period=${period}`),
}

export const adjustmentsApi = {
  listProposed: () => request("/plan-adjustments?status=proposed"),
  get: (id) => request(`/plan-adjustments/${id}`),
  respond: (id, action) => request(`/plan-adjustments/${id}/respond`, { method: "POST", body: { action } }),
}

export const notificationsApi = {
  list: () => request("/notifications"),
  markRead: (id) => request(`/notifications/${id}/read`, { method: "PUT" }),
}
