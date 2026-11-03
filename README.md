# IIT Ropar Facility Booking

An online replacement for IIT Ropar's paper facility booking workflow, built in four weekly increments
(see the LLD, Appendix A).

**Current state: Week 3.** Submission with reference numbers, availability and conflict prevention, and the
Facilities, Academic and Sports approval desks, on top of Week 2's sign-in and draft requests. The database is **PostgreSQL**; it was switched from MongoDB after Week 1 feedback.

| Layer      | Stack                                                    |
| ---------- | -------------------------------------------------------- |
| Frontend   | React 18 + TypeScript, Vite, React Router                |
| Backend    | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic          |
| Database   | PostgreSQL 14+ (psycopg 3 driver), Alembic migrations    |
| Sign-in    | Google OAuth 2.0 / OpenID Connect (google-auth verifies the ID token) |

## What's built

### Week 1: foundation and catalogue
- Versioned REST API (`/api/v1`), env-based configuration, CORS and one error format
  (`{"error": {"code", "message", "details"}}`).
- `GET /health` (200 when PostgreSQL answers, 503 when it doesn't); `503 DATABASE_UNAVAILABLE` from any endpoint
  if the database goes down.
- `GET /facilities` and `GET /facilities/{code}`: catalogue with slots and today's tariffs.
- Alembic migrations with foreign keys and check constraints; idempotent seed (10 facilities, 33 tariffs, 16 slots).
- Responsive catalogue page.

### Week 2: sign-in, requester form, drafts
- **Google sign-in** (authorization-code flow). The backend:
  - checks a random `state` to stop forged callbacks;
  - exchanges the one-time code with Google using the client secret;
  - verifies the ID token: Google's signature, our client ID as audience, issuer, expiry and the `nonce`;
  - requires a verified email.

  The browser never supplies the identity.
- **Rate category:**
  - Emails ending exactly in `@iitrpr.ac.in` get **IIT** automatically and skip the category page. Lookalikes such as
    `@notiitrpr.ac.in` and subdomains such as `@cse.iitrpr.ac.in` don't qualify.
  - Other users choose **Govt./Semi Govt./PSU** or **Private** once, and can change it later.
  - The API refuses `IIT` as a choice, so the browser can't claim the IIT rate.
- **Sessions:** a random token in an `HttpOnly`, `SameSite=Lax` cookie. Only its SHA-256 hash is stored in the
  `sessions` table, and sign-in expires after 7 days. Every POST/PUT/PATCH/DELETE must also send the session's
  **CSRF token** in an `X-CSRF-Token` header.
- **Requester pages:** sign-in, organisation category, home, My requests, request detail.
- **Booking form:**
  - **Step 1, event details:** organisation, person booking, contacts, purpose, participants. The email comes from
    Google and is read-only.
  - **Step 2, facilities:** add, edit and remove several facilities, each with its own date and slot. The slot list
    depends on the facility; only the Auditorium complete space offers half days. Each line shows the reviewing
    section and the user's rate, with a running subtotal.
- **Drafts:** create, view, edit event details, add/edit/remove lines, delete the draft. Everything is stored in
  PostgreSQL.
- **Validation on the server:**
  - required fields and phone numbers;
  - participants must be a whole number above 0;
  - the facility must be active and the slot must belong to it (also enforced by a composite foreign key);
  - no past dates, and at most 365 days ahead;
  - a tariff must exist for the user's category on that date;
  - lines in one request can't overlap (same facility, same date, overlapping times);
  - unknown fields such as `user_id`, `rate_category` or `status` are rejected.
- **Privacy:** users only ever see their own requests. Anyone else's request answers 404.
- **Tariff preview** comes from the backend: the rate for the user's category on each line's date, plus the subtotal.
  It's labelled as indicative; GST, cleaning, deposit and electricity come in Week 4.

### Week 3: submission, availability, approval workflow
- **Step 3, review and submit:** the requester checks everything, reads the terms and ticks "I accept". The server
  refuses a submission without the current terms version (`TERMS_REQUIRED`, `TERMS_OUTDATED`).
- **Reference numbers** `FB-YYYY-NNN`, issued atomically by PostgreSQL (`INSERT … ON CONFLICT` on a per-year
  counter), so two requests submitted at the same moment never share a number. A returned request keeps its number.
- **Snapshots at submission:** each line stores the facility name, section, slot, rate category, tariff and amount
  used. Later tariff or catalogue changes don't alter submitted requests.
- **Availability:** `GET /availability?facility_id=&date=` shows which slots are already booked. Step 2 greys out
  booked slots. The server checks again at submission (`SLOT_UNAVAILABLE`) and at confirmation.
- **Conflict prevention in the database:** a confirmed line creates a row in `reservations` with a time range. A
  PostgreSQL **exclusion constraint** (`btree_gist`, `facility_id =` and `during &&`) makes two overlapping
  reservations for one facility impossible, even if two staff confirm at the same instant. Adjacent ranges such as
  the Auditorium's first and second halves are allowed.
- **Facilities desk:** sees submitted requests. It can **forward** a request (it goes to every section that has
  lines) or **return** it for correction with a reason. The requester edits a returned request and resubmits.
- **Academic and Sports desks:** see only forwarded requests with undecided lines for their own section. They
  **confirm** or **reject** each line; rejecting needs a remark.
- **Mixed requests** (for example LHC + cricket ground) go to both sections at once. Each decides only its own
  lines; the server answers 403 for the other section's lines.
- **When every line is decided:** at least one confirmed line → `WITH_ESTATE` (ready for Week 4 costing); all lines
  rejected → `REJECTED`. Rejected lines drop out of the subtotal.
- **Roles on the server:** every desk endpoint checks the role (`403 FORBIDDEN`). The frontend hides desks you don't
  have, but that's only for convenience. Roles are granted by email with a command (see Setup).
- **Audit timeline:** submitted, returned, resubmitted, forwarded, line confirmed or rejected, and status changes,
  each with who, which role, when and any remark. Requesters see it on their request; staff see it on the desk.

**Deferred (per the plan):** Estate electricity estimate, costing, advance intimation, emails, admin (Week 4).

## API

All under `/api/v1`. 🔒 = needs a signed-in session; ✍️ = also needs the `X-CSRF-Token` header.

| Method & path | Purpose |
| --- | --- |
| `GET /health` | API and database status |
| `GET /facilities`, `GET /facilities/{code}` | Catalogue |
| `GET /auth/config` | Whether Google / development sign-in are available |
| `GET /auth/google` | Starts Google sign-in (redirects to Google) |
| `GET /auth/callback` | Google redirects here; sets the session cookie, then redirects to the frontend |
| `POST /auth/logout` ✍️ | Ends the session |
| `GET /users/me` 🔒 | Signed-in user, rate category and CSRF token |
| `PUT /users/me/rate-category` ✍️ | External users choose `GOVT` or `PRIVATE` |
| `GET /requests` 🔒 | My requests |
| `POST /requests` ✍️ | Create a draft from event details |
| `GET /requests/{id}` 🔒 | Draft with lines and tariff preview |
| `PATCH /requests/{id}` ✍️ | Edit event details (drafts only) |
| `DELETE /requests/{id}` ✍️ | Delete a draft |
| `POST /requests/{id}/lines` ✍️ | Add a facility line |
| `PATCH /requests/{id}/lines/{line_id}` ✍️ | Change a line's facility, date or slot |
| `DELETE /requests/{id}/lines/{line_id}` ✍️ | Remove a line |
| `GET /requests/terms` 🔒 | Current terms and conditions, with their version |
| `POST /requests/{id}/submit` ✍️ | Submit or resubmit (`{"terms_accepted": true, "terms_version": "…"}`) |
| `GET /requests/{id}/events` 🔒 | Timeline of my own request |
| `GET /availability?facility_id=&date=` 🔒 | Which slots of a facility are booked on a date |
| `GET /workflow/queue?desk=FACILITY\|ACADEMIC\|SPORTS` 🔒 staff | Requests waiting for that desk |
| `GET /workflow/requests/{id}` 🔒 staff | A request as staff see it, with the allowed actions and the timeline |
| `POST /requests/{id}/forward` ✍️ Facilities | Send to the sections |
| `POST /requests/{id}/return` ✍️ Facilities | Return for correction (`{"reason": "…"}`) |
| `POST /requests/{id}/decision` ✍️ Academic/Sports | `{"line_id", "decision": "CONFIRMED"\|"REJECTED", "remark"}` |

Interactive docs: http://localhost:8000/docs

## Database schema

```text
facilities ──< facility_slot_types ──< tariffs        (Week 1: master data)
     │                 └──────────────< slot_windows
     │                                     │ (facility_id, slot_key)
users ──< sessions                         │
  └────< requests ──< request_lines ───────┘        (Week 2)
            │              └──── reservations        (Week 3: confirmed lines only, no overlaps)
            └──< status_events                       (Week 3: audit timeline)
staff_roles (email, role)   reference_counters (year, last_value)
```

Rules the database enforces:
- **Uniqueness:** facility codes; one Google account and one email per user.
- **Allowed values:** group, section, category, unit and request status.
- **Valid references:**
  - every tariff, slot window and request line points at a real facility;
  - a tariff only exists for a unit the facility supports;
  - a request line's slot belongs to its facility (composite foreign key).
- **Value checks:**
  - non-negative amounts and positive participants;
  - lowercase emails;
  - a tariff's end date is after its start; a slot's start time is before its end;
  - the same facility/date/slot can't appear twice in one request;
  - a rejected line must have a remark; a decision is PENDING, CONFIRMED or REJECTED;
  - **no two reservations for one facility may overlap in time** (exclusion constraint `ex_reservations_no_overlap`).

Models live in `backend/app/db/models.py`. Migrations live in `backend/alembic/versions/` (`0001_master_data`,
`0002_users_and_requests`, `0003_workflow`). A test fails if the models and migrations disagree.

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (EDB installer on Windows; remember the `postgres` password)

### 1. Google OAuth client (one-time, about 10 minutes)
1. Create a project in **console.cloud.google.com**.
2. Go to **APIs & Services → OAuth consent screen** (or **Google Auth Platform**). Choose **External**, enter an
   app name and support email, then add your test accounts under **Audience → Test users**.
3. Go to **Clients / Credentials → Create OAuth client ID → Web application**. Add the authorised redirect URI
   `http://localhost:8000/api/v1/auth/callback`.
4. Copy the client ID and secret into `backend/.env` (next step). Never commit them.

### 2. Backend
```bash
cd backend
pip install -r requirements-dev.txt
cp .env.example .env        # Windows: copy .env.example .env
```
Edit `backend/.env`:
- the PostgreSQL password in both database URLs;
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`;
- `APP_SECRET_KEY`, set to any long random string.

Then:
```bash
python -m app.db.create_database   # creates the database if missing
alembic upgrade head               # creates/updates tables (run again after pulling new migrations)
python -m app.db.seed              # master data; safe to rerun
python -m app.db.grant_role you@iitrpr.ac.in FACILITY   # staff roles (see below)
uvicorn app.main:app --reload --port 8000
```

### Staff roles
Roles are attached to an email address, so you can grant them before that person has ever signed in.
```bash
python -m app.db.grant_role someone@gmail.com ACADEMIC
python -m app.db.grant_role someone@gmail.com SPORTS
python -m app.db.grant_role someone@gmail.com ACADEMIC --revoke
python -m app.db.grant_role --list
```
Roles: `FACILITY`, `ACADEMIC`, `SPORTS` (plus `ESTATE` and `ADMIN`, reserved for Week 4). One account may hold
several. Sign out and back in (or refresh) to see new desks in the header.

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```
Open http://localhost:5173 and sign in.

**Use `localhost`, not `127.0.0.1`, in the browser.** The session cookie belongs to `localhost`, and the Google
redirect URI uses it too.

## Tests and checks

```bash
cd backend
pytest -v          # needs PostgreSQL; uses facility_booking_test (created, migrated and wiped automatically)
ruff check .

cd frontend
npm test
npm run typecheck
npm run build
```

Google is replaced by a fake in the backend tests, so they run without internet access or real Google accounts.

## Configuration

See `backend/.env.example` for every variable. The main ones:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL`, `TEST_DATABASE_URL` | PostgreSQL connections (test DB name must end in `_test`) |
| `APP_SECRET_KEY` | Signs the short-lived OAuth state cookie. The app refuses to start outside development with the built-in default. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OAuth client |
| `IIT_EMAIL_DOMAIN` | `iitrpr.ac.in` |
| `FRONTEND_URL` | CORS origin, and where users land after sign-in |
| `SESSION_TTL_HOURS`, `COOKIE_SECURE` | Session length; set secure cookies when served over HTTPS |
| `DEV_LOGIN_ENABLED` | Development-only sign-in without Google (see below). Off by default. |

### Development sign-in (optional)
If an account can't use the OAuth app (for example, the institute blocks unverified apps), you can set
`DEV_LOGIN_ENABLED=true` in `backend/.env`. The login page then shows a "Development sign-in" form that takes just an
email address.
- It applies the same IIT email rule as Google sign-in.
- It only works when `APP_ENV` is `development`; with any other value the endpoint answers 404.
- Use it only on your own machine, and say so when demoing.

## Week 3 demonstration script

Prepare three accounts, for example: a Gmail requester, plus your institute account with `FACILITY` and `ACADEMIC`,
and a third account with `SPORTS` (or give one account all three roles to demo alone).

1. **Migrate.** `alembic upgrade head` applies `0003_workflow`. In pgAdmin show `reservations`, `status_events`,
   `staff_roles`, `reference_counters`, and the exclusion constraint on `reservations`.
2. **Submit a mixed request.** As the requester, create a draft with **LHC Classroom M5** (full day) and
   **Cricket Ground** (a 3-hour slot). Continue to review, try submitting without ticking the terms (button
   disabled), tick it and submit. Show the reference number `FB-2026-…` and the timeline.
3. **Return for correction.** As Facilities, open the **Facilities desk**, open the request and **Return for
   correction** with a reason. As the requester, show the reason, edit, and **Review and resubmit**. The reference
   number is unchanged and the timeline shows "returned" then "resubmitted".
4. **Forward.** As Facilities, forward it. It leaves the Facilities queue and appears on **both** the Academic and
   Sports desks.
5. **Per-line decisions.** As Academic, only the M5 line has Confirm/Reject. Confirm it. In http://localhost:8000/docs
   show that Academic deciding the cricket line gets 403. As Sports, try **Reject** with no remark (refused), then
   reject with a remark. The request moves to **With Estate** (one line confirmed); the requester sees each line's
   decision, the remark and the full timeline.
6. **Conflict prevention.** As another requester, open step 2 for M5 on the same date: the full-day slot shows
   "(already booked)". Show the database refusing an overlap: `pytest -k overlap -v`.
7. **Roles.** A requester who opens `/desk/facilities` sees "Staff only"; calling `/workflow/queue` directly
   answers 403.

## Assumptions and design notes

1. **Database:** PostgreSQL, switched from MongoDB after Week 1 feedback. Week 3 will use a PostgreSQL exclusion
   constraint to make overlapping confirmed bookings impossible.
2. **Drafts need complete event details.** Step 1 must be valid before a draft exists; lines are added in step 2.
3. **Only confirmed lines hold a slot.** Drafts, submitted and pending lines reserve nothing; availability is
   checked at submission and again when a section confirms. The first confirmation wins.
4. **Drafts preview today's tariffs.** Tariffs, the rate category and facility names are snapshotted at submission.
5. **Booking window:** from today up to 365 days ahead, in India time (IST). Confirm with Facilities.
6. **Contact email** is the verified Google email and can't be edited (LLD §19 item 11, to be confirmed).
7. **External users can change their category** from Home. Submitted requests (Week 3) will keep the category they
   were submitted with.
8. **Slot times are placeholders** until Facilities confirms them: Auditorium halves 09:00–13:00 and 14:00–18:00;
   sports 3-hour windows 09:00–12:00, 12:00–15:00 and 15:00–18:00.
9. **The Auditorium foyer** is shown as full day, because the presentation doesn't define its slot.
10. **No official data has been invented:** no payment URL or staff emails. The terms text is a clearly labelled
    placeholder (version `v1-placeholder`) until Facilities supplies the approved text.
11. **Partial rejection:** if at least one line is confirmed, the request continues to Estate with only the
    confirmed lines; it is `REJECTED` only when every line is rejected. To be confirmed with Facilities.
12. **Returned for correction** is an added state (`RETURNED`) so Facilities can send back incomplete requests.
    The requester can edit everything and resubmit; the reference number stays the same.
13. **Staff roles are keyed by email** and granted with a command; an admin page comes in Week 4.
14. **Facilities forwards the whole request;** each line goes to the section that owns its facility.

## Known limitations

- Requests stop at **With Estate**: Estate's electricity estimate, costing and advance intimation are Week 4.
- No email notifications yet (Week 4); staff check their desk queues.
- Roles are managed from the command line; there is no admin page yet (Week 4).
- While the Google app is in "Testing" mode, only accounts listed as test users can sign in.
