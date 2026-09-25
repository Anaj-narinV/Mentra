# Mock layer — swap-out point

Everything in this folder is temporary stand-in data. `src/api/client.js` is
the ONLY place that imports from here. When a real backend is available:

1. Set `USE_MOCKS = false` at the top of `src/api/client.js`.
2. Point `BASE_URL` in the same file at the real backend.
3. Delete this folder once no longer needed for local dev/demo.

No screen or component imports `mocks/` directly — they only ever call
functions from `src/api/index.js`, so this swap is a one-file change.
