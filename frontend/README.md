# ElderLink frontend

React + TypeScript + Vite caregiver UI: **Care** (what changed), **Timeline**, **Handoff** and **Care Circle**,
plus the voice recorder that uploads audio to S3 through a presigned URL.

```bash
cp .env.example .env.local       # set VITE_ELDERLINK_API_URL to the deployed API
npm install
npm run dev                      # always http://localhost:5173 (strictPort)
npm run build                    # type-check + production build
npm run lint
```

- The deployed API and S3 bucket allow CORS **only** from `http://localhost:5173`, so the dev server is pinned to
  that port and errors if it is busy (stop the other server with `kill $(lsof -ti tcp:5173)`).
- `VITE_ELDERLINK_USE_MOCK_DATA=true` runs entirely on `src/data/mockEvents.ts`. In that mode the recorder
  never sends audio anywhere; it just adds a canned event.
- The browser never receives a transcription API key or AWS credentials. Do not add any `VITE_*` secret.
- Microphone access needs `localhost` or HTTPS, and the browser's permission prompt to be allowed.
