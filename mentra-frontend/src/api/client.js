// Single choke point for all backend communication.
// Screens/components NEVER call fetch() or an AI provider directly — only
// functions exported from src/api/index.js, which all route through here.

import * as mock from "../mocks/mockData.js"

// Phase 3: the real FastAPI backend now implements every endpoint this
// client calls (see backend/README.md for the full contract). Mocks are
// kept as a fallback/dev reference (per the Phase 3 plan) and can be
// re-enabled by setting VITE_USE_MOCKS=true in a local .env file — nothing
// else in the app needs to change either way.
const USE_MOCKS = import.meta.env?.VITE_USE_MOCKS === "true"
const BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000"
const LATENCY_MS = 500

function delay(ms = LATENCY_MS) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function getToken() {
  return localStorage.getItem("mentra_token")
}

async function realRequest(path, { method = "GET", body } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = new Error(`Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.json()
}

// Mock router: maps a path+method to canned mock data. Kept intentionally
// simple (string matching) since it only exists for local dev/demo.
async function mockRequest(path, { method = "GET", body } = {}) {
  await delay()

  if (path === "/auth/login" || path === "/auth/signup") {
    return { token: "mock-token", user: mock.mockUser }
  }
  if (path === "/profile" && method === "GET") return mock.mockProfile
  if (path === "/profile" && method === "PUT") return { ok: true }
  if (path === "/onboarding" && method === "POST") return { ok: true }
  if (path === "/goals" && method === "POST") return mock.mockGoal
  if (/\/goals\/.*\/assessment$/.test(path)) return mock.mockAssessment
  if (/\/goals\/.*\/roadmap$/.test(path)) return mock.mockRoadmap
  if (/\/milestones\/.*/.test(path) && method === "PUT") return { ok: true }
  if (path.startsWith("/tasks") && method === "GET") {
    return path.includes("range") ? mock.mockTasksWeek : mock.mockTasksToday
  }
  if (/\/tasks\/.*\/status/.test(path) && method === "PUT") return { ok: true }
  if (/\/conversations\/.*\/messages$/.test(path) && method === "GET") return mock.mockMessages
  if (/\/conversations\/.*\/messages$/.test(path) && method === "POST") {
    const text = (body?.content || "").toLowerCase()
    const done = text.includes("finish") || text.includes("complet") || text.includes("done")
    const reply = done
      ? "Nice work — Ive marked that as complete. Keep this pace up and we might even move a little faster than planned."
      : "Thanks for telling me. Ive noted it — if this keeps happening this week Ill suggest lightening the load a bit."
    return {
      reply,
      task_update: done ? { task_id: "t1", status: "completed" } : null,
    }
  }
  if (path.startsWith("/progress/summary")) return mock.mockProgressSummary
  if (path.startsWith("/plan-adjustments") && method === "GET") {
    return path.includes("adj1") ? mock.mockAdjustment : [mock.mockAdjustment]
  }
  if (/\/plan-adjustments\/.*\/respond/.test(path)) return { ok: true }
  if (path === "/notifications" && method === "GET") return mock.mockNotifications
  if (/\/notifications\/.*\/read/.test(path)) return { ok: true }

  throw new Error(`No mock handler for ${method} ${path}`)
}

export async function request(path, options) {
  return USE_MOCKS ? mockRequest(path, options) : realRequest(path, options)
}
