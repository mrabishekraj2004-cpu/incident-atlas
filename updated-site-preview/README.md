# Incident Atlas — interface preview

This private ChatGPT Site is a static preview of the Incident Atlas interface. It uses authored synthetic incident and replay fixtures. It does not call the FastAPI backend, contact an AI provider, or make external changes.

The app includes a local sign-in and registration prototype, a persistent light/dark theme choice, and a settings page for appearance, workspace details, notifications, integrations, and data boundaries. The forms do not create or verify server accounts. Password fields are discarded without being transmitted or stored; only a display name and email are kept in the current browser session. This app-level prototype is separate from the ChatGPT Site's own access gate.

The UI identifies its data as a **static fixture preview**. Stored reports are labeled as replays; live AI is unavailable; approval confirmations are local to the browser and are not persisted to PostgreSQL. No external system can be changed from this Site.

The application files and public fixtures were adapted from `shaviJayasingha/incident-atlas` main commit `8f0097efac9c69d84ac2060a7a00b4d0a1932432`. This Site-only build enables fixtures only when both `VITE_STATIC_FIXTURE_PREVIEW=true` and `VITE_DATA_MODE=fixtures` are set.

## Local build

```powershell
npm ci
$env:VITE_DATA_MODE = "fixtures"
$env:VITE_STATIC_FIXTURE_PREVIEW = "true"
npm run build
```
