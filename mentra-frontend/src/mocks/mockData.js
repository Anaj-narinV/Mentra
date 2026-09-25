// Isolated mock dataset. Nothing outside src/mocks and src/api/client.js
// should ever import this directly — see src/mocks/README.md.

export const mockUser = { id: "u1", name: "Jana", email: "jana@example.com" }

// onboarding_complete: true so mock-mode login (§Login.jsx) lands on
// /dashboard like a returning user, rather than looping back into
// onboarding on every mock login — mock data represents an established user.
export const mockProfile = {
  daily_routine: "College 9-4, free evenings",
  available_time: "45 minutes",
  preferred_schedule: "evenings",
  existing_knowledge: "Basic Python",
  constraints: ["College classes"],
  preferences: ["Short daily sessions"],
  onboarding_complete: true,
}

export const mockGoal = {
  id: "g1",
  title: "Learn Data Structures & Algorithms for placements",
  target_outcome: "Clear technical interviews at product companies",
  current_level: "Comfortable with basic Python, new to DSA",
  target_date: "2026-12-15",
  status: "active",
}

export const mockAssessment = {
  goal_id: "g1",
  ai_summary:
    "Youre starting from a solid coding foundation but DSA itself is new territory, and youre doing this alongside a full course load. Thats a real constraint, not a weakness — so Ive kept daily sessions short and focused rather than long and exhausting. Well build pattern recognition first (arrays, strings, hashing) before touching anything that needs a whiteboard.",
  difficulty_level: "Moderate — foundational concepts, steady pace",
  recommended_workload: "45\u201360 minutes on college days, up to 90 on weekends",
}

export const mockRoadmap = {
  goal_id: "g1",
  milestones: [
    {
      id: "m1",
      title: "Arrays, Strings & Hashing",
      target_date: "2026-10-05",
      status: "in_progress",
      progress_pct: 40,
      tasks_preview: ["Two-pointer patterns", "Sliding window basics", "HashMap frequency problems"],
    },
    {
      id: "m2",
      title: "Recursion & Backtracking",
      target_date: "2026-10-26",
      status: "upcoming",
      progress_pct: 0,
      tasks_preview: ["Recursion fundamentals", "Subsets & permutations", "Backtracking on grids"],
    },
    {
      id: "m3",
      title: "Trees & Graphs",
      target_date: "2026-11-23",
      status: "upcoming",
      progress_pct: 0,
      tasks_preview: ["Binary tree traversals", "BFS/DFS", "Graph shortest paths"],
    },
    {
      id: "m4",
      title: "Mock Interviews & Review",
      target_date: "2026-12-10",
      status: "upcoming",
      progress_pct: 0,
      tasks_preview: ["Timed mock rounds", "Weak-topic revision"],
    },
  ],
}

export const mockTasksToday = [
  {
    id: "t1",
    milestone_id: "m1",
    title: "Sliding window: max subarray sum",
    description: "Solve 3 problems using the fixed-size sliding window pattern.",
    priority: "high",
    estimated_duration: "45 min",
    due_date: "2026-09-22",
    status: "pending",
  },
  {
    id: "t2",
    milestone_id: "m1",
    title: "Review: two-pointer notes",
    description: "Quick re-read of yesterdays two-pointer summary before todays set.",
    priority: "low",
    estimated_duration: "10 min",
    due_date: "2026-09-22",
    status: "completed",
  },
]

export const mockTasksWeek = [
  ...mockTasksToday,
  {
    id: "t3",
    milestone_id: "m1",
    title: "HashMap frequency problems",
    description: "Solve 4 problems using hashmap counting patterns.",
    priority: "medium",
    estimated_duration: "50 min",
    due_date: "2026-09-24",
    status: "pending",
  },
  {
    id: "t4",
    milestone_id: "m1",
    title: "Weekly recap quiz",
    description: "Short self-check quiz on this weeks patterns.",
    priority: "medium",
    estimated_duration: "20 min",
    due_date: "2026-09-26",
    status: "rescheduled",
  },
]

export const mockMessages = [
  {
    id: "msg1",
    sender: "ai",
    content: "Hey Jana — how did todays sliding window set go?",
    created_at: "2026-09-22T09:00:00Z",
  },
]

export const mockProgressSummary = {
  daily: { tasks_completed: 1, tasks_missed: 0, consistency_pct: 100 },
  weekly: {
    tasks_completed: 5,
    tasks_missed: 2,
    consistency_pct: 71,
    goal_progress_pct: 18,
    trend: "Youve completed 5 of your last 7 tasks.",
    streak_days: 4,
  },
  monthly: { tasks_completed: 18, tasks_missed: 5, consistency_pct: 78, goal_progress_pct: 18 },
  upcoming: mockTasksToday.filter((t) => t.status === "pending"),
}

export const mockAdjustment = {
  id: "adj1",
  status: "proposed",
  trigger_reason: "You missed 3 tasks this week, mostly around college submissions.",
  change_summary: "Id like to lighten tomorrows workload and push the recap quiz to the weekend.",
  expected_effect: "Keeps you on the same overall target date without the daily crunch.",
  current_plan: ["Sliding window set (45 min)", "Weekly recap quiz (20 min)"],
  proposed_plan: ["Sliding window set — shortened (25 min)", "Recap quiz moved to Saturday"],
}

export const mockNotifications = [
  { id: "n1", type: "adjustment", message: "Mentra has a plan adjustment for you to review.", related_task_id: null, is_read: false, created_at: "2026-09-22T08:00:00Z" },
  { id: "n2", type: "task_due", message: "Todays sliding window set is due by 8pm.", related_task_id: "t1", is_read: false, created_at: "2026-09-22T07:00:00Z" },
  { id: "n3", type: "milestone", message: "Youre 40% through Arrays, Strings & Hashing.", related_task_id: null, is_read: true, created_at: "2026-09-20T07:00:00Z" },
]
