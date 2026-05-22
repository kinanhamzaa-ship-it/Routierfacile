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
- **NEW Leave-period cycle rule**: when a new entry is added and ≥6 full
  inactive days separate it from the previous entry, the system:
  1. Closes the current open work cycle.
  2. Inserts an empty `is_leave_period: true` cycle covering the entire
     absence (leave_start_date, leave_end_date, leave_days).
  3. Opens a fresh new cycle for the new entry.
- Leave detection is **skipped on back-dating** (entries existing after the
  new date inhibit the rule).
- Dashboard exposes `leave_period` (most recent leave cycle between previous
  work cycle and current cycle) and `previous_cycle` now filters out leave
  cycles to always compare against the last real work cycle.
- Frontend: `LeavePeriodBanner` shown above PreviousCycleCard when a leave
  period exists.
- Tests: `/app/backend/tests/test_leave_cycle.py` (16 passing) covers the
  full contract including boundary gap_days=5 vs 6.

## Next Tasks
- (P1) PWA support (manifest + service worker).
- (P1) PDF export for custom date ranges.
- (P2) Refactor server.py into routers.
