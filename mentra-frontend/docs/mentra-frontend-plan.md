# Mentra — Phase 2: UI & Frontend Plan
**Prepared by: Claude Member 3 — UI & Frontend**
Built on the approved Requirements & Architecture Foundation. Core concept, data model, and API shapes are unchanged.

**Design direction:** Mentra should read as a mentor's workspace, not a task-tracker or generic chatbot. A warm, calm, editorial feel — the mentor's own words (assessment, chat, proposals) are set in a distinct serif voice; everything systemic (tasks, dashboard numbers, forms) stays in a plain, legible sans. One accent color is reserved for "the mentor is speaking or deciding something" so it never feels arbitrary.

- **Color:** `--bg #F3F5F0` (soft sage-paper, not stock cream) · `--surface #FFFFFF` · `--ink #1F2A24` (deep forest-charcoal, not pure black) · `--primary #2F4B3C` (forest green — trust/growth) · `--primary-light #4F6F5B` · `--accent #B98B3E` (warm ochre — mentor/AI signal only, used sparingly) · `--line #DDD8CC` (hairline borders) · status: success `#3F7A5C`, warning `#B9793E`, danger `#B23B3B`, muted `#8A8578`
- **Type:** *Fraunces* (serif, warm, opinionated) for screen titles and the mentor's own voice — assessment summary, chat bubbles from Mentra, adjustment proposal headline. *Public Sans* (clean humanist sans) for everything else — nav, forms, task lists, dashboard numbers, buttons.
- **Layout:** Left sidebar nav on desktop (collapses to a bottom tab bar on mobile — 5 destinations max). Content column max-width ~760px, left-aligned, generous line-height. Chat gets a full-height dedicated panel, not a corner widget — it's a primary surface, not a support tool.
- **Principles:** (1) serif = mentor's voice, sans = system, never mixed within one sentence; (2) the ochre accent appears only where the AI is speaking or asking for a decision — nowhere else; (3) dashboard shows five numbers, not fifteen; (4) a plan-adjustment proposal is a distinct card type the user must act on, never a passive toast.

---

## A. Complete Screen Map

| # | Screen | Route |
|---|---|---|
| 1 | Login | `/login` |
| 2 | Signup | `/signup` |
| 3 | Onboarding (multi-step) | `/onboarding` |
| 4 | Goal Creation | `/goals/new` |
| 5 | AI Assessment Result | `/goals/:goalId/assessment` |
| 6 | Roadmap | `/roadmap` |
| 7 | Daily / Weekly Tasks | `/tasks` |
| 8 | Conversational Progress (Chat) | `/chat` |
| 9 | Progress Dashboard | `/dashboard` |
| 10 | Plan Adjustment Proposal | `/adjustments/:id` (also embeds as a card on Dashboard/Tasks) |
| 11 | Notifications | `/notifications` |

## B. Navigation Flow

```
/login or /signup
     │
     ▼ (success)
first-time? ──yes──▶ /onboarding ──▶ /goals/new ──▶ /goals/:id/assessment ──▶ /roadmap (first view, "roadmap generated")
     │no
     ▼
/dashboard  ◀────────────────────────────────────────────────────────────────┐
     │  (default landing page after login for returning users)               │
     │                                                                       │
Main nav (persistent sidebar / bottom tabs), 5 destinations:                 │
  [Dashboard] [Roadmap] [Tasks] [Chat] [Notifications]                       │
                                                                              │
Tasks/Dashboard → tapping a pending PlanAdjustment card → /adjustments/:id   │
  → respond (accept/edit/decline) → back to origin screen, data refreshed ──┘
```

- **After login:** returning users land on `/dashboard`. New users are routed into onboarding first.
- **After onboarding:** straight into Goal Creation (goal is the thing onboarding was collecting context for) → Assessment → Roadmap.
- **Reaching today's tasks:** `/tasks` is a top-level nav item; Dashboard's "today" card also deep-links there.
- **Opening the mentor conversation:** `/chat` is a top-level nav item, always one tap away — reinforces it as primary, not buried.
- **Viewing progress:** `/dashboard` top-level nav item.
- **Reviewing adaptive plan changes:** surfaced two ways — (1) a banner/card on Dashboard and Tasks whenever a `PlanAdjustment` is `proposed`, (2) a badge on Notifications — both link to `/adjustments/:id`.

No more than 5 nav destinations; Login/Signup/Onboarding/Goal Creation/Assessment/Adjustment are flow steps, not nav items.

## C. Screen-by-Screen UI Specification

### 1–2. Login / Signup
- **Purpose:** authenticate.
- **Content:** email + password fields (signup adds name); single primary action.
- **Actions:** submit; switch between login/signup.
- **Components:** `TextField`, `Button`, `AuthCard`.
- **Data needed:** none in. Out: JWT + user id.
- **API:** `POST /auth/login`, `POST /auth/signup`.
- **Loading:** button shows inline spinner, disabled. **Empty:** n/a. **Error:** inline message under the form ("That email/password doesn't match — try again," never a raw server message). **Success:** redirect per §B.

### 3. Onboarding (multi-step)
- **Purpose:** collect routine/time/preference context the AI needs (§11 of architecture) — separate from the goal itself.
- **Content:** stepped form — daily routine, available time per day, preferred schedule, existing knowledge/constraints, preferences. One question-group per step, progress indicator at top (not numbered 01/02/03 — a simple filled progress bar).
- **Actions:** next / back per step; submit on last step.
- **Components:** `StepIndicator`, `TextField`, `Chip` (multi-select for constraints/preferences), `Button`.
- **Data needed:** none in. Out: profile payload.
- **API:** `PUT /profile`, `POST /onboarding`.
- **Loading:** step transitions are instant (client-side); final submit shows a full-panel spinner ("Setting things up…"). **Empty:** n/a. **Error:** inline per-field validation; submit error shown as a banner with retry. **Success:** advance to Goal Creation.

### 4. Goal Creation
- **Purpose:** capture the goal itself.
- **Content:** goal title, target outcome, current level, target date, existing knowledge for this goal.
- **Actions:** submit → triggers Assessment.
- **Components:** `TextField`, `DatePicker`, `TextArea`, `Button`.
- **Data needed:** out: goal payload.
- **API:** `POST /goals`.
- **Loading:** on submit, transitions straight to Assessment screen in a loading state (assessment is generated as part of this call's follow-through — see Data Flow §H). **Empty:** n/a. **Error:** banner + retry, form data preserved. **Success:** navigate to `/goals/:id/assessment`.

### 5. AI Assessment Result
- **Purpose:** show the mentor's read of the user before committing to a roadmap — this is the first "mentor voice" moment.
- **Content:** serif-set summary paragraph (`ai_summary`), plus a plain-sans breakdown: current level, difficulty, recommended workload, a short "what this means for your plan" line.
- **Actions:** "Continue to roadmap" (primary); no editing here — editing happens on the roadmap itself.
- **Components:** `MentorMessageBlock` (serif card, ochre accent rule), `SummaryStatRow`, `Button`.
- **Data needed:** in: `GET /goals/:id/assessment`.
- **API:** `GET /goals/:id/assessment`.
- **Loading:** skeleton text block ("Mentra is thinking about your goal…"). **Empty:** shouldn't occur (assessment always follows goal creation) — fallback CTA to retry generation. **Error:** banner + retry. **Success state:** content shown, CTA active.

### 6. Roadmap
- **Purpose:** show the plan's shape — the "map" the mentor built.
- **Content:** goal title + target date at top; vertical milestone timeline (title, target date, status, % of its tasks done); current milestone visually emphasized.
- **Actions:** expand a milestone to see its weekly objectives/tasks; edit a milestone's title/date/order (per architecture's "basic user editing").
- **Components:** `MilestoneTimeline`, `MilestoneItem` (expandable), `EditableField`.
- **Data needed:** in: `GET /goals/:id/roadmap`.
- **API:** `GET /goals/:id/roadmap`, `PUT /milestones/:id`.
- **Loading:** skeleton timeline. **Empty:** "No roadmap yet" + CTA back to goal creation (edge case only). **Error:** banner + retry. **Success:** timeline rendered, current milestone highlighted.

### 7. Daily / Weekly Tasks
- **Purpose:** the day-to-day work surface; manual status is the *fallback* to chat.
- **Content:** toggle Today / This Week; task cards with title, priority, estimated duration, status badge.
- **Actions:** tap a task to see description; manual status buttons (Complete / Skip / Reschedule) as a secondary path; "Talk to Mentra about this" link → opens Chat pre-filled with the task in context.
- **Components:** `TaskCard`, `StatusBadge`, `ViewToggle`, `Button`.
- **Data needed:** in: `GET /tasks?date=` / `?range=`.
- **API:** `GET /tasks`, `PUT /tasks/:id/status`.
- **Loading:** skeleton cards. **Empty:** "Nothing scheduled — enjoy the break" (never blank silence). **Error:** banner + retry. **Success:** list rendered; a `PlanAdjustment` banner appears above the list if one is pending.

### 8. Conversational Progress (Chat)
- **Purpose:** core feature — natural-language progress reporting.
- **Content:** message thread, mentor replies in serif `MentorMessageBlock` bubbles, user messages in plain right-aligned bubbles; input bar at bottom; if opened from a task, a small "About: [task title]" chip above the input.
- **Actions:** send message; tap a chip suggestion (e.g. "I finished it," "I need more time") for low-friction input alongside free text.
- **Components:** `ChatThread`, `ChatBubble`, `ChatInput`, `SuggestionChip`, `TypingIndicator`.
- **Data needed:** in: `GET /conversations/:id/messages`. Out: message text.
- **API:** `GET /conversations/:id/messages`, `POST /conversations/:id/messages`.
- **Loading:** `TypingIndicator` while awaiting AI reply (never a blank wait). **Empty:** first-open shows a mentor-voice greeting prompt ("Tell me how today's going"). **Error:** failed send shows inline retry on that message, doesn't lose the draft. **Success:** reply appended; if the extraction changed a task, a small inline confirmation chip appears under that reply ("Marked 'Python practice' as complete").

### 9. Progress Dashboard
- **Purpose:** show consistency and progress in plain language, not a data-analytics screen.
- **Content:** five metrics max — today's progress, this week's completion %, consistency streak, overall goal progress %, one plain-language trend line ("You've completed 5 of your last 7 tasks"); "Upcoming" mini-list (next 3 tasks).
- **Actions:** switch period (daily/weekly/monthly); tap into Tasks or Roadmap from relevant cards.
- **Components:** `MetricCard`, `ProgressBar` (goal %), `PeriodToggle`, `UpcomingList`.
- **Data needed:** in: `GET /progress/summary?period=`.
- **API:** `GET /progress/summary`.
- **Loading:** skeleton metric cards. **Empty:** first-week state — "Your progress will show up here once you complete a few tasks," metrics shown as dashes not zeros-that-look-broken. **Error:** banner + retry. **Success:** metrics populated; pending-adjustment banner shown here too (it's the most-visited screen).

### 10. Plan Adjustment Proposal
- **Purpose:** the human-in-the-loop decision point — never silently applied.
- **Content:** mentor-voice `change_summary` and `trigger_reason` ("Based on your last week, I'd like to lighten tomorrow's load"); a simple current-plan vs proposed-plan comparison (task-by-task or date-by-date diff, whichever `change_payload` describes); "expected effect" line.
- **Actions:** Accept / Decline / Request changes (opens Chat with the adjustment as context, so "request changes" is just talking to the mentor, not a separate form).
- **Components:** `AdjustmentProposalCard` (ochre-bordered, distinct from every other card type in the app), `DiffRow`, `Button` ×3.
- **Data needed:** in: `GET /plan-adjustments/:id`. Out: response.
- **API:** `GET /plan-adjustments?status=proposed`, `POST /plan-adjustments/:id/respond`.
- **Loading:** skeleton card. **Empty:** n/a (only reached when one exists) — direct nav to a non-existent one redirects to Dashboard. **Error:** banner + retry, buttons stay disabled until resolved. **Success:** confirmation state ("Got it — tomorrow's plan is updated") then auto-return to origin screen.

### 11. Notifications
- **Purpose:** lightweight in-app list (MVP scope — no push/email).
- **Content:** reverse-chronological list — upcoming task, missed task, milestone reached, pending adjustment.
- **Actions:** tap → deep-link to the relevant screen (task, adjustment, roadmap); mark-as-read on open.
- **Components:** `NotificationItem`, `EmptyState`.
- **Data needed:** in: `GET /notifications`.
- **API:** `GET /notifications`, `PUT /notifications/:id/read`.
- **Loading:** skeleton rows. **Empty:** "Nothing new — you're all caught up." **Error:** banner + retry. **Success:** list rendered, unread visually distinct (dot, not bold-everything).

## D. Component Hierarchy

```
App
 ├─ AuthProvider / MentraDataProvider / ChatProvider  (context, §F)
 ├─ AppShell                          (sidebar/bottom-tabs + content outlet)
 │   ├─ NavSidebar / NavTabBar
 │   └─ <Outlet/>
 │       ├─ Login / Signup            (no AppShell — standalone)
 │       ├─ Onboarding                (no AppShell — standalone flow)
 │       ├─ GoalCreation
 │       ├─ AssessmentResult          uses MentorMessageBlock
 │       ├─ Roadmap                   uses MilestoneTimeline → MilestoneItem
 │       ├─ Tasks                     uses TaskCard, StatusBadge, AdjustmentBanner
 │       ├─ Chat                      uses ChatThread → ChatBubble, ChatInput
 │       ├─ Dashboard                 uses MetricCard, ProgressBar, UpcomingList, AdjustmentBanner
 │       ├─ PlanAdjustment            uses AdjustmentProposalCard → DiffRow
 │       └─ Notifications             uses NotificationItem
 └─ shared/ui: Button, TextField, TextArea, DatePicker, Chip, Card,
               LoadingState, EmptyState, ErrorState, StatusBadge, Skeleton
```

## E. Frontend Folder Structure

```
frontend/
├── index.html
├── package.json, vite.config.js, tailwind.config.js, postcss.config.js
├── src/
│   ├── main.jsx, App.jsx, index.css
│   ├── api/            # one file per backend module (§9 of architecture)
│   ├── mocks/           # isolated mock data + mock handlers — swap-out point
│   ├── state/            # AuthContext, MentraDataContext, ChatContext
│   ├── components/
│   │   ├── ui/             # Button, TextField, Card, Loading/Empty/Error states...
│   │   └── ...              # TaskCard, MilestoneItem, ChatBubble, AdjustmentProposalCard, etc.
│   └── screens/
│       ├── auth/, onboarding/, goals/, assessment/, roadmap/,
│       │ tasks/, chat/, dashboard/, adjustment/, notifications/
└── README.md
```

## F. State Management Plan

Plain **React Context + hooks** — no Redux/Zustand (NFR-2: avoid unnecessary libraries).

- **`AuthContext`**: current user, JWT, login/logout/signup actions. Persists token to `localStorage`.
- **`MentraDataContext`**: profile, active goal, assessment, roadmap, tasks, progress summary, pending adjustments, notifications — the app's core domain data, fetched on demand per screen and cached in context so switching screens doesn't re-fetch unnecessarily.
- **`ChatContext`**: message list, send state (idle/sending), isolated from `MentraDataContext` since it updates far more frequently.
- Each context exposes its own `status: 'idle'|'loading'|'success'|'error'` per resource, consumed directly by screens for the Loading/Empty/Error/Success rendering (§I).
- Forms are local component state (`useState`), validated on submit — no form library needed for this field count.

## G. API Integration Map

| Screen | Endpoint | Method | Request | Response → UI use |
|---|---|---|---|---|
| Login | `/auth/login` | POST | email, password | token → `AuthContext`, redirect |
| Signup | `/auth/signup` | POST | name, email, password | token → `AuthContext`, redirect to onboarding |
| Onboarding | `/profile`, `/onboarding` | PUT/POST | routine, time, prefs | success → redirect to Goal Creation |
| Goal Creation | `/goals` | POST | goal fields | goal id → redirect to Assessment (loading) |
| Assessment | `/goals/:id/assessment` | GET | — | `ai_summary`, difficulty, workload → `MentorMessageBlock` |
| Roadmap | `/goals/:id/roadmap` | GET | — | milestones[] → `MilestoneTimeline` |
| Roadmap edit | `/milestones/:id` | PUT | title/date/order | updates timeline item |
| Tasks | `/tasks?date=` / `?range=` | GET | — | tasks[] → `TaskCard` list |
| Task status | `/tasks/:id/status` | PUT | status | updates card badge |
| Chat history | `/conversations/:id/messages` | GET | — | messages[] → `ChatThread` |
| Chat send | `/conversations/:id/messages` | POST | text | AI reply + any task update → append bubble, refresh Tasks context |
| Dashboard | `/progress/summary?period=` | GET | — | metrics → `MetricCard`/`ProgressBar` |
| Adjustments list | `/plan-adjustments?status=proposed` | GET | — | banner visibility on Dashboard/Tasks |
| Adjustment detail | `/plan-adjustments/:id` | GET | — | proposal card content |
| Adjustment respond | `/plan-adjustments/:id/respond` | POST | accept/edit/decline | confirmation → refresh Roadmap/Tasks |
| Notifications | `/notifications` | GET | — | list |
| Notification read | `/notifications/:id/read` | PUT | — | marks item read |

**All calls go through `src/api/client.js`, never directly to an AI provider** — matches the architecture's rule that the frontend only ever talks to the backend.

## H. Frontend Data Flow

```
Onboarding:      form submit → api/profile → MentraDataContext.profile set → navigate

Assessment:      GoalCreation submit → api/goals.create → returns goal
                 → navigate to /goals/:id/assessment (loading state shown immediately)
                 → api/goals.getAssessment → MentraDataContext.assessment set → render

Roadmap gen:     (triggered server-side after assessment in this architecture;
                 frontend just does) api/roadmap.get → MentraDataContext.roadmap set → render

Daily tasks:     api/tasks.list → MentraDataContext.tasks set → TaskCard list render

Chat progress:   user types → ChatContext optimistic-appends user bubble
                 → api/conversation.sendMessage → backend runs extraction
                 → response { reply, taskUpdate? } → ChatContext appends AI bubble
                 → if taskUpdate present, MentraDataContext.tasks patched in place
                 (no full re-fetch needed)

Progress extract: (backend/AI internal — frontend only ever sees the resulting
                 chat reply + optional task patch above)

Adjustment
 proposal:       MentraDataContext polls/derives `hasPendingAdjustment` from
                 api/adjustments.list on Dashboard/Tasks mount → banner shown

Accept/reject:   api/adjustments.respond → on success, MentraDataContext
                 re-fetches roadmap + tasks (they may have changed) → UI updates

Dashboard:       api/progress.summary(period) → MetricCard render
```

## I. Loading / Error / Empty State Strategy

- **Loading:** every async screen shows a skeleton shaped like its final content (skeleton cards for Tasks/Dashboard, skeleton text block for Assessment, `TypingIndicator` for Chat) — never a bare spinner on its own for content-bearing screens. Buttons show an inline spinner + stay disabled during their own submit.
- **Empty:** every list screen defines a specific, in-voice empty message (see §C per screen) — never just a blank area.
- **Error:** a single reusable `ErrorState`/inline banner pattern: plain-language explanation + a **Retry** action that re-runs the same request. Failed form submits preserve entered data.
- **Success:** default rendered state; mutating actions (status update, adjustment response, chat send) get a brief inline confirmation (a toast or inline chip) rather than a full-page change, so the user doesn't lose place.
- **Retry:** centralized in `api/client.js` — a failed request returns a typed error the calling screen can re-trigger; no ad-hoc retry logic duplicated per screen.

## J. Implementation Order

1. Project scaffold (Vite + Tailwind + design tokens) + shared `ui/` primitives + `AuthContext` + Login/Signup (unblocks everything else, and is the smallest vertical slice).
2. `api/client.js` + `mocks/` (isolated, swappable) — every screen from here builds against this contract, backend or not.
3. Onboarding → Goal Creation → Assessment (the setup funnel).
4. Roadmap + Tasks (the daily-use core).
5. Chat (highest-complexity UI, but independent of Roadmap/Tasks internals once Tasks exists for context-linking).
6. Plan Adjustment Proposal (depends on Tasks/Roadmap existing to diff against).
7. Dashboard (can be built with mock `ProgressSnapshot` data any time after step 2; wire last since it reads from everything else).
8. Notifications (lowest dependency — build any time after step 2, in parallel with the above).

---

# HANDOFF TO BACKEND + AI

**Screens completed (spec + implementation):** Login, Signup, Onboarding, Goal Creation, AI Assessment Result, Roadmap, Daily/Weekly Tasks, Conversational Progress (Chat), Progress Dashboard, Plan Adjustment Proposal, Notifications — all 11, per §A–C.

**Components created:** `AppShell` (nav), full `ui/` primitive set (Button, TextField, TextArea, DatePicker, Chip, Card, Skeleton, EmptyState, ErrorState, StatusBadge), plus domain components — `MentorMessageBlock`, `MilestoneTimeline`/`MilestoneItem`, `TaskCard`, `ChatThread`/`ChatBubble`/`ChatInput`, `MetricCard`/`ProgressBar`, `AdjustmentProposalCard`, `NotificationItem`.

**API contracts needed from Backend:** exactly the endpoint list in §G — no additions, no gaps. Response shapes assumed match the entity fields in the Architecture doc §8.

**Data required from Backend for each screen:** listed per-screen in §C ("Data required from backend").

**AI interactions required (all via Backend, never called directly by frontend):** goal assessment generation, roadmap generation, chat reply + progress extraction, plan-adjustment proposal generation — frontend only renders their structured results, never their logic.

**Remaining integration work:** replace `src/mocks/*` calls in `src/api/*` with real `fetch` calls to the live backend base URL (the mock/real boundary is isolated exactly for this — see `src/mocks/README` in the code); confirm real response field names match §8 exactly, since the UI binds to those field names directly; wire real JWT issuance/refresh into `AuthContext` (currently mock-token based).
