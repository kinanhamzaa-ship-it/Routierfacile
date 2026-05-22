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

## Backlog (P1/P2)
- P1: Weekly rest auto-check (≥45h consecutive). Multi-week comparisons.
- P1: PDF export for arbitrary date range.
- P1: PWA install (manifest + service worker).
- P2: Multi-driver fleet view for managers.
- P2: i18n (English).
- P2: Photo upload for receipts (object storage).
- P2: Auto-calculated réglementaire EU (4h30 driving → 45min break).
- P2: Push reminders end-of-day.

## Next Tasks
- Run testing subagent end-to-end.
- Address blocking issues.
- Deliver MVP screenshot to user.
