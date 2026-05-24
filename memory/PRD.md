# Routier Facile — PRD

## Original Problem Statement
Production-ready mobile-first SaaS web application "Routier Facile" for truck drivers in Europe.
Daily manual driving logbook + compliance dashboard. Drivers enter their work at end of day; system calculates driving hours, working hours, rest, weekly totals, monthly summaries.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). JWT auth via PyJWT + bcrypt.
- **Frontend**: React (CRA) + Tailwind + shadcn/ui + Phosphor icons + Recharts + jsPDF.
- **Theme**: Dark Performance Pro — Barlow Condensed (display) + Inter (body), high-contrast tactical UI.
- **Language**: French.

## User Personas
- **Conducteur (driver)**: Logs daily activity at end of shift, monitors weekly 56h limit, tracks meal indemnity and découcher counts for payroll.

## Core Requirements (static)
- Daily entry: date, start/end time, multiple driving segments, multiple rest breaks, departure/arrival, notes, découcher (bool), meal status (yes/no/unsure).
- Automatic calcs: total driving, total working, total rest, amplitude.
- Weekly: total driving vs 56h, remaining, OK/Warning/Risk indicator.
- Monthly: total driving, working days, rest, découcher count, meal counters.
- Sticky Compliance Dashboard always visible (week + daily rest + month indicators).
- History: list, search, edit, delete.
- PDF export of monthly summary.
- Auth: register + login (JWT bearer token).
- Mobile-first, dark mode.

## What's been implemented (2026-02-XX, MVP)
- JWT auth (register, login, logout, me) with bcrypt + admin seed.
- DailyEntry CRUD with unique-per-day constraint.
- Summary endpoints: dashboard, week, month.
- Frontend routes: /login, /register, /, /new, /edit/:id, /history, /monthly.
- Sticky ComplianceBar with 56h progress + status indicators.
- Bottom navigation (4 tabs).
- EntryForm with multi-segment driving + rest, toggles for découcher & meal.
- Monthly page with Recharts bar chart + PDF export (jsPDF + autoTable).
- History with full-text search and per-day editing.

## Update v2 (2026-02-XX, Cycle-based compliance)
- Separated **Amplitude** vs **Heures travaillées** (shown live in form + dashboard + history + PDF).
- Auto-computed **daily rest** (previous end → current start) with status OK ≥11h, Reduced ≥9h <11h, Warning <9h.
- **Cycle model** (`cycles` collection): replaces ISO week. Each entry attached to current cycle.
- Counters per cycle: `reduced_rest_used` (max 3), `extensions_used` (10h driving, max 2).
- **Weekly rest detection** endpoint `/api/cycles/detect-rest`: signals `weekly_rest_full` (≥45h) or `weekly_rest_reduced` (24–45h). Frontend shows RestDetectionModal — user always confirms.
- Endpoints: `/api/cycles/current`, `/api/cycles/start-new`, `/api/cycles/confirm-reduced`.
- Legacy entries (pre-cycle) marked `is_legacy=true`, shown in history with archive badge, excluded from cycle counters.
- Dashboard "Today" snapshot section with amplitude / worked / driving / rest tiles.
- History shows full breakdown per entry including coloured `daily_rest_status`.
- PDF export updated with amplitude + worked + previous rest columns.

## Backlog (P1/P2)
- P1: Weekly rest auto-check (≥45h consecutive). Multi-week comparisons.
- P1: PDF export for arbitrary date range.
- P1: PWA install (manifest + service worker).
- P2: Multi-driver fleet view for managers.
- P2: i18n (English).
- P2: Photo upload for receipts (object storage).
- P2: Refactor server.py into auth/entries/cycles/summary routers (now ~795 lines).
- P2: Auto-calculated réglementaire EU (4h30 driving → 45min break).
- P2: Push reminders end-of-day.

## Update v3 (2026-02, Empty cycles + Leave-period cycles)
- **No empty cycles** policy enforced: a cycle is created lazily only when a
  new entry is added, and deleted as soon as its last entry is removed.
- **Auto-revert** on last-entry delete: the most recent closed WORK cycle is
  reopened (`ended_at=null`, `is_reduced_weekly_rest=false`). Leave cycles are
  skipped when reverting.
- **Dashboard tolerates `cycle=null`**: ComplianceBar renders an "Aucun cycle
  actif" empty state when no cycle is open; PreviousCycleCard is only shown
  when both cycle + previous_cycle are present.
- **Leave-period cycles** are a **pure projection** of inactivity gaps in
  the entry timeline. `reconcile_leave_cycles(user_id)` runs after every
  entry create/update/delete: deletes leave cycles whose covered range no
  longer matches a current gap and creates new ones for any gap ≥ 6 days.
- `maybe_close_cycle_on_leave_gap` (called inside `create_entry`) closes the
  open work cycle when a chronological add lands ≥ 6 days after the previous
  entry, so the new entry starts a fresh work cycle.
- Dashboard `previous_cycle` no longer filters out leave cycles — when a
  leave cycle is the most recently closed, it surfaces as the comparison
  reference with **0h00** totals (acting as a reset point). The dict carries
  `is_leave_period`, `leave_start_date`, `leave_end_date`, `leave_days`.
- Frontend: `LeavePeriodBanner` (orange info card) and `PreviousCycleCard`
  badges the leave period and swaps the date range.

## Update v4 (2026-02, Hard cap: 6 working days per cycle)
- **Hard constraint**: a non-leave cycle MUST contain at most 6 working-day
  entries. The 7th `POST /api/entries` against the same open cycle is
  rejected with HTTP 400 and a structured detail body carrying `code`,
  `title`, `headline`, `message`, `max_days`.
- The mandatory-rest wording is fixed: "Le cycle en cours contient déjà 6
  journées travaillées (maximum autorisé). Vous devez prendre votre repos
  hebdomadaire obligatoire (normal ou réduit) avant de pouvoir continuer."
- The leave-gap path (≥ 6 inactive days) closes the current cycle BEFORE the
  cap check, so a long-absence return naturally lands in a fresh cycle.
- `PUT` and `DELETE` are not affected.
- Dashboard surfaces the cap via `cycle.days_worked_max = 6`. ComplianceBar
  displays `Jours · X / 6` (orange at the cap).

## Update v5 (2026-02, Strict EU rest-compliance gate)
- `/api/cycles/start-new` and `/api/cycles/confirm-reduced` now REQUIRE a
  `DetectIn` payload `{date, start_time}` and validate the rest gap from the
  previous entry's end:
  - `start-new` requires gap ≥ 45h (full weekly rest).
  - `confirm-reduced` requires gap ≥ 24h (reduced weekly rest).
  - Missing payload → 422. Insufficient gap → 400 `{code: "rest_required",
    message, required_minutes, actual_minutes}`. No previous entry → 400
    `rest_required` with no metric fields.
- A new cycle can NEVER be opened without a real, data-detectable rest. The
  cap modal in `NewEntry` now shows only a single "J'ai compris"
  acknowledgement button — manual cycle creation from the UI is gone.
- Tests: `/app/backend/tests/test_rest_gap_contract.py` (11 PASS) + 41
  prior tests = 52/52 PASS, 0 FAIL.

## Update v6 (2026-02, Mobile-first + PWA)
- Installable PWA: `manifest.json` (standalone, portrait, dark theme, app
  icons 192/512 + maskable + 180 Apple touch) and a lightweight
  `service-worker.js` registered post-load. SW caches the app shell + static
  assets but **never** caches `/api/` calls.
- iOS / Android meta tags: `viewport-fit=cover`, `maximum-scale=1`,
  `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`,
  `apple-mobile-web-app-title`, `apple-touch-icon`.
- Safe-area-inset handling: BottomNav uses `env(safe-area-inset-bottom)`,
  shell uses `100dvh` + `rf-safe-top`.
- iOS auto-zoom on focus eliminated by enforcing `font-size: 16px` globally
  for `input/select/textarea`.
- Touch ergonomics: `touch-action: manipulation`, transparent tap-highlight,
  `min-h-[56px]` on bottom nav tabs, responsive padding on Login/Register.

## Update v7 (2026-02, Email verification via Brevo SMTP)
- `/auth/register` no longer auto-logs in: returns `{email, email_verified:false, message}`. Verification email sent (24h-TTL single-use token, HMAC-SHA256 at rest, TTL index on `expires_at`).
- `/auth/login` returns 403 `{code:"email_not_verified", message, email}` until verified.
- New endpoints: `POST /auth/verify-email`, `POST /auth/resend-verification` (generic 200, 60s cooldown, no enumeration).
- Backfill: existing users without `email_verified` field get `false` on startup. Admin is the only system-managed exception (auto-verified).
- Mail transport: stdlib `smtplib` in `asyncio.to_thread`. SSL 465 / STARTTLS 587. When SMTP env vars unset → logged WARNING no-op with the URL.
- Frontend: `/verify-pending`, `/verify-email?token=...`, resend block on `/login`. `VerifyEmail` guarded with `useRef` against StrictMode double-fire.

## Update v9 (2026-02, Email transport: SMTP → Brevo HTTP API)
- Reason: SMTP send was timing out on Render (egress restrictions on
  outbound SMTP ports). Switched to Brevo's Transactional Email REST API,
  which only uses HTTPS.
- Transport: `httpx.AsyncClient` POST to `https://api.brevo.com/v3/smtp/email`
  with `api-key` header. 15s total / 5s connect timeout.
- Env: single new var `BREVO_API_KEY`. Sender pinned to
  `noreply@routierfacile.com` ("Routier Facile") with optional overrides
  via `BREVO_SENDER_EMAIL` / `BREVO_SENDER_NAME`. Legacy `SMTP_*` env vars
  are obsolete.
- Removed: `smtplib`, `ssl`, `EmailMessage`, `asyncio.to_thread` imports.
- Regression: 25/25 email-flow tests + 70 prior tests still PASS.

## Update v10 (2026-02, Verification email + reset-link URL hardening)
- **Root cause of "reset link 404"**: link generation was using
  `APP_BASE_URL` which on Render pointed at the backend (or was empty),
  yielding `<backend>/reset-password?...` which has no such route.
  Switched to `FRONTEND_URL` (preferred) with `APP_BASE_URL` kept as a
  fallback for back-compat. Helper: `_frontend_base_url()`. Production
  value: `FRONTEND_URL=https://www.routierfacile.com`.
- **Verification + reset are now 100% symmetric**: both call
  `_send_brevo_email(..., log_label="verification" | "reset")` through the
  same async httpx path. Per-flow `try/except` wraps so an unexpected
  exception cannot silently break the caller.
- **Stronger logging**: every send now emits ONE of three labelled lines —
  `[brevo:<label>] sent OK to=… messageId=…` on success,
  `[brevo:<label>] send failed status=… body=…` on Brevo non-2xx (full
  Brevo error body included),
  `[brevo:<label>] HTTP request failed` on network errors.
- **`register` returns `email_sent: bool`** so the client knows whether the
  email actually left the server. The user message stays the same.
- **Error guard for missing FRONTEND_URL**: if neither `FRONTEND_URL` nor
  `APP_BASE_URL` is set, the sender logs an `ERROR` and aborts — no broken
  link is ever sent to a user.
- Regression: 25/25 email-flow tests still PASS. No backend / cycle /
  dashboard / PDF logic changed.
- Reason: SMTP send was timing out on Render (egress restrictions on
  outbound SMTP ports). Switched to Brevo's Transactional Email REST API,
  which only uses HTTPS.
- Transport: `httpx.AsyncClient` POST to `https://api.brevo.com/v3/smtp/email`
  with `api-key` header. 15s total / 5s connect timeout.
- Env: single new var `BREVO_API_KEY`. Sender pinned to
  `noreply@routierfacile.com` ("Routier Facile") with optional overrides
  via `BREVO_SENDER_EMAIL` / `BREVO_SENDER_NAME`. Legacy `SMTP_*` env vars
  are obsolete.
- Errors: Brevo non-2xx responses log
  `[brevo] send failed status=<code> to=<email> body=<json>` (full Brevo
  error body included, e.g. `{"message":"Key not found","code":"unauthorized"}`).
  Network errors log via `[brevo] HTTP request failed` with traceback. The
  caller flow (register / forgot-password) is NEVER blocked by transport
  failures — emails are best-effort.
- Dev/preview no-op preserved: when `BREVO_API_KEY` is unset the sender
  logs a WARNING with the verification / reset URL so devs can grab the
  token from the backend log (used by all 25 email-related tests).
- Removed: `smtplib`, `ssl`, `EmailMessage`, `asyncio.to_thread` imports.
  HTML / text bodies extracted into pure helper functions
  (`_verification_email_bodies`, `_password_reset_email_bodies`) so the
  transport swap was a true 1:1 replacement.
- Regression: 25/25 email-flow tests + 70 prior business-logic tests still
  PASS. Verified live against Brevo with a deliberate invalid key — the
  401 response was captured and logged with the structured error body.

## Update v8 (2026-02, Forgot password + Delete account + No Emergent branding)
- **Forgot password**: `POST /auth/forgot-password {email}` (generic 200,
  no enumeration, 60s cooldown) and `POST /auth/reset-password {token,
  new_password}`. Tokens HMAC-SHA256-hashed at rest, **1h TTL** via Mongo
  `expireAfterSeconds=0`, single-use. New frontend pages `/forgot-password`
  and `/reset-password`; "Mot de passe oublié ?" link on `/login`.
- **Delete account**: `DELETE /auth/me {password}` requires the current
  password for confirmation. Returns 403 `{code:"invalid_password"}` on
  mismatch, 200 with `{deleted_entries, deleted_cycles}` on success. Purges
  the user doc + entries + cycles + email_verification_tokens +
  password_reset_tokens, and clears the auth cookie. New `/account` page
  with a "Zone dangereuse" delete confirmation modal; reachable from the
  Dashboard via a `UserGear` icon.
- **Emergent branding removed**: dropped the inline `#emergent-badge`
  anchor and the `emergent-main.js` CDN script from `index.html`. Defensive
  CSS hides any future re-injection (`#emergent-badge, a[href*="emergent.sh"]
  { display: none !important }`). Verified 0 occurrences on /login,
  /dashboard, /account, /verify-email, /forgot-password.
- Tests: `/app/backend/tests/test_forgot_password_and_delete.py` (12 PASS,
  including HMAC hash check, cooldown, single-use, full account purge with
  Mongo inspection). **Regression: 70/70 prior tests still PASS.**
- Installable PWA: `manifest.json` (standalone display, portrait, dark theme,
  `start_url=/`), `service-worker.js` (network-first for HTML, cache-first
  for static; **never caches `/api/`**), registered after page load so it
  never blocks first paint.
- iOS / Android polish: `viewport-fit=cover`, `maximum-scale=1`,
  `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`,
  `apple-mobile-web-app-title`, `apple-touch-icon` (180/192/512 PNG icons +
  maskable 512).
- Safe-area-inset handling: `BottomNav` uses `rf-safe-bottom`, shell uses
  `rf-safe-top` + `100dvh`; Emergent badge offset by `env(safe-area-inset-bottom)`.
- iOS auto-zoom on focus eliminated by enforcing `font-size: 16px` on all
  inputs/selects/textareas globally.
- Touch ergonomics: `touch-action: manipulation`, transparent tap-highlight,
  `min-h-[56px]` on bottom nav tabs, responsive padding `px-5 sm:px-6` on
  Login/Register.
- `index.html` title and description updated to "Routier Facile — Carnet de
  route" so installed PWA shows the right name.
- No backend changes, no business-logic changes, no breaking test fixtures.
- `/api/cycles/start-new` and `/api/cycles/confirm-reduced` now REQUIRE a
  `DetectIn` payload `{date, start_time}` and validate the rest gap from the
  previous entry's end:
  - `start-new` requires gap ≥ 45h (full weekly rest).
  - `confirm-reduced` requires gap ≥ 24h (reduced weekly rest).
  - Missing payload → 422. Insufficient gap → 400 `{code: "rest_required",
    message, required_minutes, actual_minutes}`. No previous entry → 400
    `rest_required` with no metric fields.
- A new cycle can NEVER be opened without a real, data-detectable rest. The
  cap modal in `NewEntry` now shows only a single "J'ai compris"
  acknowledgement button — manual cycle creation from the UI is gone.
- Tests: `/app/backend/tests/test_rest_gap_contract.py` (11 PASS) + 41
  prior tests = 52/52 PASS, 0 FAIL.
- **No empty cycles** policy enforced: a cycle is created lazily only when a
  new entry is added, and deleted as soon as its last entry is removed.
- **Auto-revert** on last-entry delete: the most recent closed WORK cycle is
  reopened (`ended_at=null`, `is_reduced_weekly_rest=false`). Leave cycles are
  skipped when reverting.
- **Dashboard tolerates `cycle=null`**: ComplianceBar renders an "Aucun cycle
  actif" empty state when no cycle is open; PreviousCycleCard is only shown
  when both cycle + previous_cycle are present.
- **Leave-period cycles** are now a **pure projection** of inactivity gaps in
  the entry timeline:
  - `reconcile_leave_cycles(user_id)` runs after every entry create/update/
    delete. It deletes any leave cycle whose covered range no longer matches a
    current gap and creates new ones for any gap ≥ `LEAVE_THRESHOLD_DAYS = 6`.
  - `maybe_close_cycle_on_leave_gap` (called inside `create_entry`) closes the
    open work cycle when a chronological add lands ≥ 6 days after the previous
    entry, so the new entry starts a fresh work cycle.
- Dashboard `previous_cycle` no longer filters out leave cycles — when a leave
  cycle is the most recently closed, it surfaces as the comparison reference
  with **0h00** totals (acting as a reset point). The dict carries
  `is_leave_period`, `leave_start_date`, `leave_end_date`, `leave_days` so the
  frontend can label and date it correctly.
- Frontend: `LeavePeriodBanner` (orange info card) is rendered when
  `data.leave_period` is present; `PreviousCycleCard` swaps the date range and
  badge when `prev.is_leave_period`.
- Tests: `/app/backend/tests/test_leave_cycle.py` + `test_leave_reconciliation.py`
  (29 passing) cover the full contract including bidirectional reconciliation
  on create/update/delete, boundaries (gap 5 vs 6), stress sequences and
  work-cycle invariants.

## Next Tasks
- (P1) PWA support (manifest + service worker).
- (P1) PDF export for custom date ranges.
- (P2) Refactor server.py into routers.
