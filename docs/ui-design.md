# Incident Atlas interface design

**Status:** Current frontend design record  
**Scope:** React/Vite visitor experience, including local preview access and preferences.

## Product direction

Incident Atlas is an incident investigation workspace. The interface prioritizes fast scanning, evidence provenance, and the human approval boundary. It keeps the incident library and replay journey usable without an account or API key. Account screens personalize a local preview only; they are not connected to an authentication service.

## Visual system

| Element | Decision |
|---|---|
| Brand | Text-only “Incident Atlas” wordmark. No logo asset or decorative logo symbol. |
| Light surfaces | Warm gray `#f4f6f8` canvas, white workspace panels, graphite text, and quiet gray borders. |
| Accent | Cobalt `#315eb5` for primary actions, focus, and selected navigation. It does not signal severity or confidence. |
| Dark surfaces | Graphite `#151a20` canvas, layered slate panels, light text, and accessible pale cobalt actions. |
| Status colors | Red, amber, and green remain reserved for severity, warnings, errors, and success states, always paired with text. |
| Typography | System sans-serif for interface copy and monospace for hashes, IDs, and telemetry metadata. No remote font dependency. |
| Layout | Fixed desktop workspace rail, compact navigation at tablet widths, task-focused cards, and stacked mobile settings/forms. |
| Motion | Short interaction transitions; `prefers-reduced-motion` disables animation and smooth scrolling. |

## Pages and interactions

| Page | Experience |
|---|---|
| `/` | Product overview, provenance summary, and three synthetic scenarios. |
| `/incidents` | Search, severity filtering, replay availability, and incident cards. |
| `/incidents/:incidentId` | Symptoms, timeline, service dependencies, telemetry tabs, and links to stored or permitted investigations. |
| `/investigations/:reportId` | Stored replay provenance, ranked uncertain hypotheses, source-linked evidence, and report metadata. |
| `/investigations/:reportId/mitigation` | Human review, explicit simulation-only acknowledgment, and the resulting approval state. |
| `/methodology` | Synthetic data limitations, replay/live distinction, evaluation explanation, and illustrative service states. |
| `/login` | Preview-only sign-in form. It accepts a throwaway password solely for local form interaction; it is discarded and never sent or saved. |
| `/register` | Preview-only registration form that creates a browser-session display profile, not an account. |
| `/settings/profile` | Edit local display name and email. |
| `/settings/workspace` | Local workspace label and display timezone preference; source incident times stay UTC. |
| `/settings/appearance` | Persistent light/dark theme and session-only density preference. |
| `/settings/notifications` | Session-only preference controls; no messages or notifications are sent. |
| `/settings/integrations` | Read-only connection inventory; no credentials or live integrations are configured. |
| `/settings/privacy` | Explains browser storage and data boundaries, exports preview settings, or clears the local profile. |

The primary navigation remains available to guests. Settings links preserve a clear indication that values are local preview preferences. Sign-out ends the browser-session profile and does not delete incident approvals.

## Authentication and data boundaries

- There is no account backend, authentication provider, password storage, or server-side profile persistence in this frontend.
- Login and registration pages visibly explain the preview boundary and warn visitors not to enter a real password.
- Passwords are read only for client-side validation and are discarded on submission; only display name and email are held in `sessionStorage`.
- Appearance is held in `localStorage`; other preview preferences use `sessionStorage`.
- Settings do not configure production services. Integrations are informational and disabled.
- Fixture, API, stored replay, and live investigation provenance continue to come from the existing data adapter and API contracts. Failed API requests never fall back silently to fixtures.

## Accessibility and responsive behavior

Pages use semantic navigation, main content, labeled form fields, visible focus rings, keyboard-operable buttons and links, announced status/errors, and text labels alongside status colors. At tablet widths, the rail becomes a compact top navigation; settings sections become a responsive grid, and forms and integration cards reflow at phone widths. A reduced-motion rule suppresses animation and smooth scrolling.
