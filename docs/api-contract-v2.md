# API contract v2 — Nani AI on AWS

**Status: the v1 contract is unchanged. Everything the frontend already handles still works.**

This document lists only what is *added* or *different*. For the full Episode object, states, enums, error codes, nullability rules and mock-file conventions, `client/api-contract.md` from the existing repo remains the source of truth — copy it into the new repo as-is.

**Frozen as of Sep 3.** Any change gets logged in section 6.

---

## 1. What does NOT change

Neeraj should read this first: **almost nothing.**

- All 12 states, same names
- The full Episode object shape
- Every endpoint path and method
- All enumerated values
- Error codes and the `error` object
- Polling behaviour (3s while active, stop in terminal states)
- Mock payloads 01–09

The backend is being rebuilt on AWS. The API surface is deliberately identical so the UI does not need rework.

---

## 2. The only required frontend change

```
NEXT_PUBLIC_API_BASE_URL=<new AWS endpoint>
```

That's it. Because `output: 'export'` bakes env vars in at build time, this needs a rebuild and redeploy — it is not a runtime config change.

Keep `NEXT_PUBLIC_USE_MOCKS=true` until the AWS backend is live.

---

## 3. Endpoints

Unchanged from v1, except the new `confirm` endpoint (section 4).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/patients` | List demo patient profiles |
| `GET` | `/api/episodes?patient_id=` | List episodes for a profile |
| `POST` | `/api/episodes` | Upload prescription (`file` + `patient_id`) |
| `GET` | `/api/episodes/{id}` | Full episode object (poll while active) |
| `POST` | `/api/episodes/{id}/confirm` | **NEW** — confirm or correct the extracted tests |
| `POST` | `/api/episodes/{id}/report` | Upload lab report (fallback path) |
| `POST` | `/api/episodes/{id}/retry` | Retry after `NEEDS_HUMAN` |
| `POST` | `/api/tick` | Internal — EventBridge Scheduler only |

---

## 4. Extraction confirmation step (NEW — build this, it is core scope)

This is a real addition to the state machine, not a stretch goal. **Neeraj should build this.**

### Why it exists

Handwriting extraction is good but not perfect. On real prescriptions the agent reads the
test list reliably, but misreads dates and vitals. It must not spend the patient's money on
the strength of its own unverified read of a doctor's handwriting.

So: the agent extracts, shows the patient what it read, and **waits for confirmation before
booking anything.** This is the soft counterpart to `NEEDS_HUMAN` — proceed, but verify first.

### 4.1 New state

```
PRESCRIPTION_RECEIVED → TESTS_IDENTIFIED → AWAITING_CONFIRMATION → LABS_SHORTLISTED → …
```

UI label for `AWAITING_CONFIRMATION`: **"Confirm what we read"**

This is a **terminal-until-acted-on** state. Stop polling. Nothing else happens until the
patient confirms or corrects.

### 4.2 New endpoint

#### `POST /api/episodes/{episode_id}/confirm`

Request:
```json
{
  "tests": [
    { "test_code": "CBC", "display_name": "Hb% TC DC ESR", "urgency": "routine", "keep": true },
    { "test_code": "FBS", "display_name": "Sugar (F)", "urgency": "routine", "keep": true },
    { "test_code": "VITD", "display_name": "25 OH D", "urgency": "routine", "keep": false },
    { "test_code": "FT4TSH", "display_name": "FT4, TSH", "urgency": "urgent", "keep": true }
  ]
}
```

Response `200`: the episode object, state advanced to `LABS_SHORTLISTED`.

Send back the full list with `keep` flags rather than only the kept ones — it lets the backend
record what the patient rejected, which is useful signal.

The patient may also edit `display_name` and toggle `urgency`. Both are optional; if
unchanged, send them back as received.

### 4.3 New field on the Episode object

```json
"confirmation": {
  "required": true,
  "confirmed_at": null,
  "extracted_tests": [
    { "test_code": "CBC", "display_name": "Hb% TC DC ESR", "urgency": "routine" }
  ],
  "confirmed_tests": null,
  "edits_made": null
}
```

After confirmation, `confirmed_at` is set, `confirmed_tests` holds the final list, and
`edits_made` is an integer count of changes the patient made.

`confirmation` is null in states before `TESTS_IDENTIFIED`.

### 4.4 UI requirements

The confirmation screen shows:

- **The test list, each row editable and removable.** This is the important part — tests drive
  every downstream step.
- **The prescription image alongside it**, so the patient can check against the original.
  Without this the confirmation is meaningless.
- An urgency toggle per test (urgent / routine)
- A clear primary action: **"Confirm and find labs"**
- A secondary action: **"I need to re-upload"** → returns to upload

**Do NOT display these fields, even though the API returns them:**
- `date` — the model misreads DD.MM.YY dates and asserts them confidently. Use the upload
  timestamp for anything user-facing.
- `exam_findings` — vitals are misread (a real BP of 140/80 came back as PR 110/80). Showing
  a wrong blood pressure in a health app is worse than showing nothing.

Both are extracted and stored for completeness. Neither is trustworthy enough to show.

`medicines`, `complaint`, `diagnosis` and `patient` can be shown read-only as context, but
they are not editable and do not drive anything.

### 4.5 New timeline entries

```json
{ "at": "...", "actor": "intake_agent", "action": "awaiting_confirmation",
  "detail": "4 tests read from prescription — asked patient to confirm" }
{ "at": "...", "actor": "patient", "action": "confirmed_tests",
  "detail": "3 of 4 tests confirmed, 1 removed" }
```

### 4.6 Why this earns marks

Design is one of five equally weighted criteria in this hackathon, and it asks whether the
project is a complete product experience rather than a technical proof of concept. An agent
that says "here's what I read, confirm before I book" reads as trustworthy. An agent that
silently books four tests off a handwriting guess reads as reckless — even when it's right.

Make this screen good. It is the most defensible thing in the product.

---

## 5. Coverage extension (OPTIONAL — build only if ahead of schedule)

**Do not build UI for this until Shashank confirms the backend is shipping it.** If it does not get built, none of the fields below appear and nothing breaks.

### 4.1 New endpoints

#### `POST /api/patients/{patient_id}/policy`
Upload an insurance policy PDF. Parsed once at upload; the extracted rules are stored.

Request: `multipart/form-data` with `file`.

Response `202`:
```json
{
  "policy_id": "pol_3a9f",
  "status": "PARSING",
  "insurer": null,
  "parsed_at": null
}
```

#### `GET /api/patients/{patient_id}/policy`
Poll after upload. Response `200`:
```json
{
  "policy_id": "pol_3a9f",
  "status": "PARSED",
  "insurer": "Example General Insurance",
  "plan_name": "Health Secure Individual",
  "sum_insured": 500000,
  "parsed_at": "2026-09-11T08:20:00Z",
  "opd_benefit": {
    "present": true,
    "annual_limit": 5000,
    "used_to_date": 1200
  },
  "notable_exclusions": [
    { "clause": "4.2", "summary": "Outpatient diagnostics not payable unless linked to hospitalisation" }
  ]
}
```

`status`: `PARSING` | `PARSED` | `FAILED`

### 4.2 New field on the Episode object

A `coverage` object appears alongside `prescription`, **null** when no policy is on file or the feature is off:

```json
"coverage": {
  "policy_id": "pol_3a9f",
  "checked_at": "2026-09-11T08:24:00Z",
  "total_estimated_out_of_pocket": 1150,
  "currency": "INR",
  "per_test": [
    {
      "test_code": "FERRITIN",
      "display_name": "Serum ferritin",
      "verdict": "covered",
      "clause": "3.7",
      "clause_summary": "Diagnostic tests payable under the OPD benefit",
      "estimated_cost": 650,
      "patient_pays": 0,
      "note": "Within your remaining OPD limit of ₹3,800"
    },
    {
      "test_code": "TSH",
      "display_name": "Thyroid stimulating hormone",
      "verdict": "not_covered",
      "clause": "4.2",
      "clause_summary": "Outpatient diagnostics excluded unless linked to hospitalisation",
      "estimated_cost": 450,
      "patient_pays": 450,
      "note": null
    },
    {
      "test_code": "CBC",
      "display_name": "Complete blood count",
      "verdict": "partial",
      "clause": "3.7",
      "clause_summary": "Payable up to the remaining OPD sub-limit",
      "estimated_cost": 900,
      "patient_pays": 700,
      "note": "OPD limit covers ₹200 of this test"
    }
  ]
}
```

### 4.3 New enum

- `coverage.per_test[].verdict`: `covered` | `not_covered` | `partial` | `unknown`

`unknown` means the agent could not determine coverage confidently. **Render it as uncertainty, never as "covered."**

### 4.4 New state

One addition to the state machine, between `TESTS_IDENTIFIED` and `LABS_SHORTLISTED`:

```
COVERAGE_CHECKED
```

UI label: "Checking what your insurance covers". Skipped entirely when no policy is on file — the episode goes straight from `TESTS_IDENTIFIED` to `LABS_SHORTLISTED` as before.

### 4.5 New error codes

- `POLICY_UNREADABLE` — the policy PDF could not be parsed
- `POLICY_NOT_FOUND` — coverage check attempted with no policy on file

Both retryable, both use the existing `error` object shape.

### 4.6 New timeline actor

- `timeline[].actor`: add `coverage_agent`

Example entry:
```json
{ "at": "2026-09-11T08:24:00Z", "actor": "coverage_agent", "action": "checked_coverage",
  "detail": "1 covered, 1 partial, 1 excluded — ₹1,150 out of pocket" }
```

---

## 6. Rendering guidance for coverage

If it gets built, the display rules that matter:

- **A "not covered" answer is the valuable one.** Do not hide it or style it as an error. It is useful information delivered before the patient spends money.
- **Always show the clause reference.** "Clause 4.2" next to the verdict is what proves the agent read the document. This is the single most important visual detail in the feature.
- Show `total_estimated_out_of_pocket` prominently — it is the number a patient actually cares about.
- `unknown` gets neutral styling and honest wording ("couldn't determine"), never green.
- Costs are estimates. Label them as such.

---

## 7. Change log

- `2026-09-03` — v2 created. v1 contract unchanged; coverage extension added as optional.
- `2026-09-07` — added the extraction confirmation step (section 4) as core scope: new state `AWAITING_CONFIRMATION`, new endpoint `POST /api/episodes/{id}/confirm`, new `confirmation` field. Model extraction is reliable on the test list but misreads dates and vitals, so those are stored but not displayed.
