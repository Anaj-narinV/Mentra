# Frontend → Backend Contract Audit

Performed by inspecting `mentra-frontend.zip` directly — `src/api/client.js`
(the mock router doubles as a precise contract spec), `src/api/index.js`,
`src/mocks/mockData.js`, all three state contexts, and all 11 screens —
before any backend code was written.

Format: **Frontend expectation → endpoint → request → response → consumer**

---

### Auth
- `authApi.login/signup` → `POST /auth/login`, `POST /auth/signup`
  → req: `{email,password}` / `{name,email,password}`
  → res: `{token, user:{id,name,email}}`
  → consumer: `AuthContext` (stores token+user in `localStorage`, redirects)

### Profile / Onboarding
- `profileApi.update` → `PUT /profile` → req: partial profile fields → res: `{ok:true}` (frontend doesn't read the body)
- `profileApi.completeOnboarding` → `POST /onboarding` → req: `{daily_routine, available_time, preferred_schedule, existing_knowledge, constraints[], preferences[]}` → res: `{ok:true}` → consumer: `Onboarding.jsx`

### Goals / Assessment
- `goalsApi.create` → `POST /goals` → req: `{title, target_outcome, current_level, target_date}` → res: **full goal object including `id`** (frontend does `navigate(`/goals/${created.id}/assessment`)`, so the id must come back synchronously) → consumer: `GoalCreation.jsx`
- `goalsApi.getAssessment` → `GET /goals/:id/assessment` → res: `{goal_id, ai_summary, difficulty_level, recommended_workload}` → consumer: `AssessmentResult.jsx` (`MentorMessageBlock`, `SummaryStatRow`)

### Roadmap
- `roadmapApi.get` → `GET /goals/:id/roadmap` → res: `{goal_id, milestones:[{id,title,target_date,status,progress_pct,tasks_preview[]}]}` → consumer: `Roadmap.jsx` → `MilestoneTimeline`
- `roadmapApi.updateMilestone` → `PUT /milestones/:id` → req: partial `{title,target_date,order_index,status}` → res: `{ok:true}`
- **Note**: `Roadmap.jsx` hardcodes `GOAL_ID = "g1"` rather than looking up the user's goal dynamically (MVP: one goal per user, per Architecture §14). Documented and handled — see "Deviations" below.

### Tasks
- `tasksApi.listToday` → `GET /tasks?date=today`, `tasksApi.listWeek` → `GET /tasks?range=week` → res: `[{id,milestone_id,title,description,priority,estimated_duration,due_date,status}]` → consumer: `Tasks.jsx` → `TaskCard`
- `tasksApi.updateStatus` → `PUT /tasks/:id/status` → req: `{status}`, must be one of `pending|completed|partially_completed|skipped|rescheduled` (exact FR-9 enum) → res: `{ok:true}`

### Conversation
- `conversationApi.getMessages` → `GET /conversations/:id/messages` → res: `[{id,sender,content,created_at}]` → consumer: `Chat.jsx` → `ChatThread`/`ChatBubble`
- `conversationApi.sendMessage` → `POST /conversations/:id/messages` → req: `{content, task_id}` → res: `{reply, task_update: {task_id,status} | null}` → consumer: `ChatContext` (appends AI bubble, calls `patchTaskFromChat` if `task_update` present)
- **Note**: `ChatContext.jsx` hardcodes `CONVERSATION_ID = "c1"` (single-thread MVP). Same pattern as goal id above.

### Progress
- `progressApi.summary` → `GET /progress/summary?period=daily|weekly|monthly` → res: `{daily:{...}, weekly:{...}, monthly:{...}, upcoming:[...]}`, each period block: `{tasks_completed, tasks_missed, consistency_pct}` plus `weekly` additionally carries `goal_progress_pct`, `trend`, `streak_days` → consumer: `Dashboard.jsx` (reads `data[period]` generically, but reads `data.weekly.goal_progress_pct/trend/streak_days` specifically regardless of selected period — this exact shape had to be preserved, not "cleaned up")

### Plan Adjustments
- `adjustmentsApi.listProposed` → `GET /plan-adjustments?status=proposed` → res: **array** → consumer: banners on `Dashboard.jsx`/`Tasks.jsx`/`Roadmap.jsx` read `adjustments.data?.[0]`
- `adjustmentsApi.get` → `GET /plan-adjustments/:id` → res: **single object** `{id,status,trigger_reason,change_summary,expected_effect,current_plan[],proposed_plan[]}` → consumer: `PlanAdjustment.jsx` → `AdjustmentProposalCard`
- `adjustmentsApi.respond` → `POST /plan-adjustments/:id/respond` → req: `{action}` → res: `{ok:true}`. UI only ever sends `action: "accept"` or `"decline"` (see `domain.jsx`'s `AdjustmentProposalCard`) — "Request changes" is a `<Link to="/chat">`, not an API call.

### Notifications
- `notificationsApi.list` → `GET /notifications` → res: `[{id,type,message,related_task_id,is_read,created_at}]` → consumer: `Notifications.jsx` → `NotificationItem`
- `notificationsApi.markRead` → `PUT /notifications/:id/read` → res: `{ok:true}`

---

## Deviations from Phase 1/2 docs, and how they were resolved

1. **Phase 1 §9 lists `GET /goals` (list) and `GET /goals/:id`** — not used by
   the current frontend code, but implemented anyway since Phase 1 specifies
   them and they cost nothing to add; future screens (e.g. multi-goal, out
   of MVP scope) can use them immediately.

2. **Hardcoded singleton ids (`"g1"`, `"c1"`)** — the actual frontend code
   assumes one goal and one conversation per user and references them by a
   fixed placeholder rather than a real id, which the real backend can't
   natively satisfy (`"g1"` isn't a real UUID). Two options existed:
   (a) rewrite the affected screens/contexts to fetch the real id first, or
   (b) teach the backend to resolve a special alias. Per the phase 3
   instruction to prioritize the actual working frontend contract while
   documenting the difference, option (b) was chosen: the backend accepts
   literal `"current"` anywhere a `goal_id`/`conversation_id` path segment is
   expected and resolves it to the user's one active goal/conversation
   (creating the conversation on first access). The frontend was updated
   with the **minimum possible diff** — `GOAL_ID`/`CONVERSATION_ID` changed
   from `"g1"`/`"c1"` to `"current"` in the two files that defined them, and
   one stale `"g1"` fallback in `MentraDataContext.respondToAdjustment`
   updated the same way. No screens, components, or API function signatures
   changed.

3. **`ProgressSnapshot` (Architecture §8)** is modeled as a table (for a
   future move to precomputed/cached dashboard reads), but Phase 3's
   `/progress/summary` computes metrics live from `Task` rows on every call
   rather than reading/writing snapshot rows. This matches the architecture
   doc's own MVP guidance (§16: "none of the MVP flows require background
   job infrastructure") and keeps the numbers always current; wiring actual
   snapshot persistence is a safe, additive Phase 4+ change.

4. **`Milestone.tasks_preview`** in the mock data was a static, hand-authored
   list per milestone. The real backend derives it from actual `Task` rows
   instead (first 3 tasks belonging to that milestone), so milestones with no
   generated tasks yet show an empty preview rather than placeholder text.
   This is more honest than mock data but is a visible behavior change for
   milestones 2+ until Phase 4's real daily-task generation populates them
   (see Known Issues in the handoff doc).
