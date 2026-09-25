# Mentra — Frontend (Phase 2)

React + Vite + Tailwind implementation of the Mentra UI, built against the
approved Requirements & Architecture Foundation. Runs entirely on mock data
out of the box — see `src/mocks/README.md` for how to switch to a real
backend.

## Run locally

```
npm install
npm run dev
```

Then open the printed local URL. Sign up with any email/password (mock auth
accepts anything) to walk the full flow: onboarding \u2192 goal creation \u2192
assessment \u2192 roadmap \u2192 tasks \u2192 chat \u2192 dashboard \u2192 notifications.

## Project structure

See `docs/mentra-frontend-plan.md` (Section D/E) for the full component
hierarchy and folder structure rationale. In short:

- `src/api/` \u2014 one function group per backend module; the only layer that
  talks to `src/api/client.js`.
- `src/mocks/` \u2014 isolated mock data/responses; swap out per its own README.
- `src/state/` \u2014 three React contexts (Auth, MentraData, Chat) \u2014 no Redux.
- `src/components/` \u2014 shared UI primitives (`ui.jsx`), domain components
  (`domain.jsx`, `chat.jsx`), and the app shell/nav.
- `src/screens/` \u2014 one folder per MVP screen, matching the 11-screen map.

## Design tokens

Defined in `tailwind.config.js` (colors) and `index.html` (Fraunces + Public
Sans fonts). The mentor\u2019s own voice (assessment text, chat replies, plan
adjustment proposals) is always set in `font-serif` with the accent color;
everything else stays `font-sans` \u2014 this is the one deliberate rule that
carries the whole visual identity, see the design plan for rationale.

## Known gaps before backend integration

- Auth is mock-token based; wire real JWT issuance into `AuthContext`.
- `USE_MOCKS` in `src/api/client.js` needs to flip to `false` with a real
  `BASE_URL` once the backend is live.
- Single-goal assumption (`GOAL_ID = "g1"` hardcoded in a couple of screens)
  should be replaced once multi-goal support (future scope) is prioritized.
