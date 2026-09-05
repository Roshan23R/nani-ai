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

## 3. Endpoints — unchanged

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/patients` | List demo patient profiles |
| `GET` | `/api/episodes?patient_id=` | List episodes for a profile |
| `POST` | `/api/episodes` | Upload prescription (`file` + `patient_id`) |
| `GET` | `/api/episodes/{id}` | Full episode object (poll while active) |
| `POST` | `/api/episodes/{id}/report` | Upload lab report (fallback path) |
| `POST` | `/api/episodes/{id}/retry` | Retry after `NEEDS_HUMAN` |
| `POST` | `/api/tick` | Internal — EventBridge Scheduler only |

---

## 4. Coverage extension (OPTIONAL — build only if ahead of schedule)

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

## 5. Rendering guidance for coverage

If it gets built, the display rules that matter:

- **A "not covered" answer is the valuable one.** Do not hide it or style it as an error. It is useful information delivered before the patient spends money.
- **Always show the clause reference.** "Clause 4.2" next to the verdict is what proves the agent read the document. This is the single most important visual detail in the feature.
- Show `total_estimated_out_of_pocket` prominently — it is the number a patient actually cares about.
- `unknown` gets neutral styling and honest wording ("couldn't determine"), never green.
- Costs are estimates. Label them as such.

---

## 6. Change log

- `2026-09-03` — v2 created. v1 contract unchanged; coverage extension added as optional.
