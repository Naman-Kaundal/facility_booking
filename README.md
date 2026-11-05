# IIT Ropar Facility Booking

An online replacement for IIT Ropar's paper facility booking workflow, built in four weekly increments
(see the LLD, Appendix A).

**Current state: Week 4 (complete).** The full workflow runs end to end: a requester signs in, books several
facilities, submits; Facilities checks and forwards; Academic and Sports decide each facility; Estate enters the
electricity estimate; the server calculates the costs; Facilities sends the advance intimation with the institute
payment link; and the requester sees the final breakdown. Emails go out at each step, and admins manage settings,
roles and master data. The app never takes payments itself. The database is **PostgreSQL**; it was switched from MongoDB after Week 1 feedback.

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

### Week 4: Estate costing, advance intimation, emails, admin
- **Estate desk:** sees requests whose sections have all decided (`WITH_ESTATE`). Estate enters only the approximate
  electricity charge, with an optional note, and can revise it until the advance is sent.
- **Costing engine (backend only, LLD §9.2):**

  | Item | Formula (defaults) |
  | --- | --- |
  | Booking charges `B` | sum of the rates frozen at submission, **confirmed facilities only** |
  | GST | `B × 18%` (indicative) |
  | Cleaning | `B × 10%` |
  | Security deposit `D` | ₹5,000 per request (refundable) |
  | Electricity `E` | Estate's estimate |
  | **Total estimated cost** | `B + GST + cleaning + D + E` |
  | **Advance** | `B + GST + cleaning + D + 80% of E` |

  Amounts are rounded half-up to the paisa. The browser can't send any amount: extra fields are refused (422).
  Every input is copied into `request_costs`, so later changes to settings or tariffs never alter a costed request.
- **Facilities advance intimation:** costed requests come back to the Facilities desk (`COSTED`). Facilities checks the
  breakdown and sends the intimation (`ADVANCE_INTIMATED`) with an optional message. It's refused until an admin has
  set the payment link (`PAYMENT_URL_NOT_CONFIGURED`).
- **Requester's final view:** after the intimation, the request page shows the full breakdown, the advance and an
  **Open the institute payment page** button with the reference number to quote. Before that, costs are hidden.
- **Email notifications (LLD §14):**

  | When | Who gets an email |
  | --- | --- |
  | Submitted / resubmitted | requester (acknowledgement) and Facilities |
  | Returned for correction | requester, with the reason |
  | Forwarded | each section that has facilities, and the requester |
  | A facility decided | requester and Facilities |
  | Every section has decided | Estate (or, if all were rejected, the requester) |
  | Costs calculated | Facilities |
  | Advance intimated | requester, with the breakdown and payment link |

  - Each email is written to `email_logs` as `PENDING` in the same transaction as the action, then sent after the
    action is saved, and marked `SENT` or `FAILED` with the error. A failed email never undoes the action.
  - Failed emails are retried up to `EMAIL_MAX_ATTEMPTS` (3) times from **Admin → Email log** or with
    `python -m app.db.retry_emails`.
  - An idempotency key (event + the audit event that caused it + recipient) means retries and refreshes never send
    duplicates.
  - With `EMAIL_BACKEND=console` (the default) emails are printed in the backend terminal instead of being sent.
- **Admin pages (`ADMIN` role only, checked on the server):**
  - **Settings:** GST %, cleaning %, security deposit, % of electricity in the advance, and the payment link.
  - **Staff roles:** give, remove and restore roles by email. Admins can't remove their own admin role.
  - **Facilities & rates:** rename, set capacity, stop or allow new bookings; add a new rate from a start date (the
    old rate ends that day; submitted requests keep their rate); switch rates and slots off; change slot times.
  - **Email log:** every email with its status, number of tries and error, plus **Retry failed emails**.
  - **Change log:** every admin change with who, when, and before/after values (`admin_audit_events`).
- **Timeline** now also shows the electricity estimate, cost calculation and advance intimation.

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
| `POST /requests/{id}/electricity` ✍️ Estate | `{"electricity_estimate", "remark"}`; the server calculates every cost |
| `POST /requests/{id}/intimate` ✍️ Facilities | Send the advance intimation (`{"remark"}` optional) |
| `GET`/`PATCH /admin/settings` ✍️ Admin | Cost settings and payment link |
| `GET`/`POST /admin/staff-roles`, `PATCH /admin/staff-roles/{id}` ✍️ Admin | List, give, remove or restore roles |
| `GET /admin/facilities`, `PATCH /admin/facilities/{id}` ✍️ Admin | Facilities with all slots and rate versions |
| `POST /admin/tariffs`, `PATCH /admin/tariffs/{id}` ✍️ Admin | Add a rate from a date; switch a rate on or off |
| `PATCH /admin/slot-windows/{id}` ✍️ Admin | Slot label, times, on/off |
| `GET /admin/emails`, `POST /admin/emails/retry` ✍️ Admin | Email log and retry |
| `GET /admin/audit` 🔒 Admin | Admin change log |

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
  requests ──1 request_costs                          (Week 4: cost breakdown snapshot)
  requests ──< email_logs                             (Week 4: every email and its delivery status)
staff_roles (email, role)   reference_counters (year, last_value)
app_settings (one row: GST %, cleaning %, deposit, electricity advance %, payment link)   admin_audit_events
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
`0002_users_and_requests`, `0003_workflow`, `0004_costing_notifications_admin`). A test fails if the models and migrations disagree.

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
Roles: `FACILITY`, `ACADEMIC`, `SPORTS`, `ESTATE` and `ADMIN`. One account may hold several. Refresh the page to see
new desks in the header. Once one person has `ADMIN`, they can manage everyone else's roles from **Admin → Staff
roles**, so the command is only needed for the first admin.

### Email (optional)
By default (`EMAIL_BACKEND=console`) emails are printed in the backend terminal and listed under **Admin → Email
log**; nothing leaves your computer. To really send them, set `EMAIL_BACKEND=smtp` and the `SMTP_*` values in
`backend/.env` (for example a Gmail account with an app password: `SMTP_HOST=smtp.gmail.com`, port 587). Retry failed
emails any time with `python -m app.db.retry_emails`.

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
| `EMAIL_BACKEND` | `console` (print emails, default) or `smtp` (send them) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `EMAIL_FROM` | SMTP server and sender |
| `EMAIL_MAX_ATTEMPTS` | Tries per email before it stays failed (default 3) |

### Development sign-in (optional)
If an account can't use the OAuth app (for example, the institute blocks unverified apps), you can set
`DEV_LOGIN_ENABLED=true` in `backend/.env`. The login page then shows a "Development sign-in" form that takes just an
email address.
- It applies the same IIT email rule as Google sign-in.
- It only works when `APP_ENV` is `development`; with any other value the endpoint answers 404.
- Use it only on your own machine, and say so when demoing.

## Week 4 demonstration script (final)

Prepare: run `alembic upgrade head` (applies `0004`). Give your account `ADMIN`, `FACILITY`, `ACADEMIC`, `SPORTS`
and `ESTATE` (or split them among teammates), and use a Gmail account as the requester.

1. **Admin setup.** Open **Admin → Settings**: show the defaults (18%, 10%, ₹5,000, 80%) and set a **test** payment
   link (for example `https://example.org/test-payment`; the real one must come from Facilities). Show **Staff
   roles** and the **Change log** entry.
2. **Book.** As the requester, create a request with **LHC Classroom M5** (full day) and **Cricket Ground**, review,
   accept the terms and submit. Note the reference number. In the backend terminal, show the two emails (requester
   and Facilities).
3. **Approve.** Facilities forwards; Academic confirms M5; Sports confirms the cricket ground. The request moves to
   **With Estate** and Estate gets an email.
4. **Electricity.** On the **Estate desk**, open the request and enter ₹2,500 with a note. Show the breakdown the
   server calculated (booking charges, GST, cleaning, deposit, electricity, total, advance with 80% electricity).
   Show that the requester can't see costs yet.
5. **Advance intimation.** On the **Facilities desk** the request is now **Costed**. Send the advance intimation.
6. **Requester's final view.** As the requester: status **Advance intimated**, the final breakdown, and the payment
   button. Show the email with the breakdown and link in the backend terminal / **Admin → Email log**.
7. **Rules.** Show that changing GST in Settings doesn't change the costed request; that a new rate for M5 starting
   next week doesn't change submitted requests; and that a requester opening `/admin` sees "Staff only".
8. **Reliability.** In **Admin → Email log**, show statuses and the retry button. Run the tests:
   `pytest -v` (backend, including `tests/test_end_to_end.py`) and `npm test` (frontend).

## Assumptions and design notes

1. **Database:** PostgreSQL, switched from MongoDB after Week 1 feedback. Week 3 will use a PostgreSQL exclusion
   constraint to make overlapping confirmed bookings impossible.
2. **Drafts need complete event details.** Step 1 must be valid before a draft exists; lines are added in step 2.
3. **Only confirmed lines hold a slot.** Drafts, submitted and pending lines reserve nothing; availability is
   checked at submission and again when a section confirms. The first confirmation wins.
4. **Drafts preview today's tariffs.** Tariffs, the rate category and facility names are snapshotted at submission,
   and the whole cost breakdown is snapshotted when Estate enters the electricity estimate.
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
13. **Staff roles are keyed by email**, granted from Admin → Staff roles (or the `grant_role` command for the first admin).
14. **Facilities forwards the whole request;** each line goes to the section that owns its facility.
15. **Costing (to confirm with DR Facilities, LLD §9.1):** GST and cleaning apply to every facility type; the
    security deposit is charged once per request; the total includes 100% of the electricity estimate while the
    advance includes 80%; rounding is half-up to the paisa. All values are editable in **Admin → Settings**.
16. **No payment is processed.** The app only shows the institute payment link that an admin entered. No official
    URL or institute email address is built in; the payment link starts empty.
17. **Estate can revise** the estimate (and the costs are recalculated) until Facilities sends the intimation.
18. **Emails are sent synchronously** right after each action, with failures logged for retry, instead of using a
    separate background worker. Good enough for this scale; a queue worker could replace it later.

## Known limitations

- Payment confirmation is outside the app (no payment gateway, by design), so requests end at **Advance intimated**.
- Post-event electricity reconciliation and deposit refunds are not covered (out of scope in the LLD).
- New facilities can't be created from the admin page (only edited, switched off, re-priced and re-timed); add them
  to `seed_data.py` and run the seed.
- The terms and conditions text is still the labelled placeholder until Facilities supplies the approved text.
- While the Google app is in "Testing" mode, only accounts listed as test users can sign in.
