# 🔌 REST API Reference

The evaluation platform exposes a lightweight FastAPI REST interface for triggering runs, listing evaluation histories, retrieving test cases, and downloading regression reports.

Interactive Swagger documentation is available locally at:
`http://localhost:8000/docs`

---

## 1. Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Root service status and documentation links |
| `GET` | `/health` | Health check verifying service and database status |
| `POST` | `/evaluate` | Synchronously execute an evaluation run |
| `GET` | `/evaluations` | List historical evaluation runs (paginated) |
| `GET` | `/evaluations/{run_id}` | Retrieve comprehensive run details, metrics, and results |
| `GET` | `/evaluations/{run_id}/report` | Retrieve Markdown or JSON regression report |
| `GET` | `/test-cases` | List test cases for a dataset version |

---

## 2. Endpoint Details

### 2.1 Health Check
**`GET /health`**

Validates that the service is running and verifies active database connectivity.

#### Response (200 OK)
```json
{
  "status": "ok",
  "database_connected": true,
  "version": "0.1.0",
  "environment": "development",
  "offline_mode": false
}
```

#### Example Request
```bash
curl -X GET "http://localhost:8000/health"
```

---

### 2.2 Trigger Evaluation
**`POST /evaluate`**

Starts and synchronously executes an evaluation run across a specified dataset version, evaluating metrics, comparing against baseline, and saving results to the database.

#### Request Body Schema
```json
{
  "dataset_version": "v1",
  "baseline_run_id": "eval_7f440f134587",
  "prompt_version": "v1.0.0",
  "app_model": "gemini-3.8-flash",
  "evaluator_model": "gemini-3.8-pro",
  "offline_mode": false,
  "git_commit": "a1b2c3d"
}
```

#### Response (201 Created)
```json
{
  "run_id": "eval_55fde013debc",
  "passed_quality_gate": true,
  "total_cases": 21,
  "duration_seconds": 1.25,
  "metrics": {
    "faithfulness": 0.997,
    "answer_relevance": 0.87,
    "context_precision": 0.977,
    "citation_validity": 1.0,
    "refusal_accuracy": 1.0,
    "schema_validity": 1.0
  },
  "failure_reasons": [],
  "report_paths": {
    "json_path": "/app/reports/regression_report_eval_55fde013debc.json",
    "markdown_path": "/app/reports/regression_report_eval_55fde013debc.md"
  }
}
```

#### Example Request
```bash
curl -X POST "http://localhost:8000/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_version": "v1",
    "offline_mode": true
  }'
```

---

### 2.3 List Historical Evaluations
**`GET /evaluations`**

Retrieves a paginated list of historical evaluation runs ordered by creation timestamp descending.

#### Query Parameters
- `limit` (integer, default: 20, min: 1, max: 100): Number of records to return.
- `offset` (integer, default: 0, min: 0): Number of records to skip.

#### Response (200 OK)
```json
[
  {
    "run_id": "eval_55fde013debc",
    "dataset_version": "v1",
    "prompt_version": "v1.0.0",
    "prompt_hash": "f047ddcf9a9c42bf",
    "app_model": "gemini-3.8-flash",
    "evaluator_model": "gemini-3.8-pro",
    "status": "PASSED",
    "passed_quality_gate": true,
    "baseline_run_id": "eval_7f440f134587",
    "git_commit": null,
    "created_at": "2026-10-15T09:58:31.123456Z",
    "completed_at": "2026-10-15T09:58:31.987654Z"
  }
]
```

---

### 2.4 Get Evaluation Run Details
**`GET /evaluations/{run_id}`**

Retrieves complete run details including aggregate metric scores and individual test case outcomes.

#### Response (200 OK)
```json
{
  "run_id": "eval_55fde013debc",
  "dataset_version": "v1",
  "prompt_version": "v1.0.0",
  "prompt_hash": "f047ddcf9a9c42bf",
  "app_model": "gemini-3.8-flash",
  "evaluator_model": "gemini-3.8-pro",
  "status": "PASSED",
  "passed_quality_gate": true,
  "baseline_run_id": "eval_7f440f134587",
  "git_commit": null,
  "created_at": "2026-10-15T09:58:31Z",
  "completed_at": "2026-10-15T09:58:31Z",
  "metrics": [
    {
      "metric_name": "faithfulness",
      "score": 0.997,
      "threshold": 0.85,
      "passed": true
    }
  ],
  "results": [
    {
      "test_case_id": "NORM-001",
      "question": "What is the mandatory data retention period for audit logs?",
      "generated_answer": "Production audit logs must be retained for 365 days in tamper-proof immutable storage.",
      "cited_sources": ["sec-audit-101"],
      "is_refusal": false,
      "passed_deterministic": true,
      "ragas_faithfulness": 0.985,
      "ragas_answer_relevancy": 0.912,
      "ragas_context_precision": 0.95,
      "execution_time_ms": 14.5,
      "error_message": null
    }
  ]
}
```

---

### 2.5 Retrieve Regression Report
**`GET /evaluations/{run_id}/report`**

Downloads the rendered report in Markdown or JSON format.

#### Query Parameters
- `format` (string, default: `markdown`): Either `markdown` or `json`.

#### Example Request
```bash
# Retrieve Markdown report
curl -X GET "http://localhost:8000/evaluations/eval_55fde013debc/report?format=markdown"

# Retrieve JSON report
curl -X GET "http://localhost:8000/evaluations/eval_55fde013debc/report?format=json"
```

---

### 2.6 List Available Test Cases
**`GET /test-cases`**

Returns all validated test cases in the specified dataset version directory.

#### Query Parameters
- `version` (string, default: `v1`): Dataset version directory tag.

#### Response (200 OK)
```json
[
  {
    "id": "NORM-001",
    "category": "normal",
    "question": "What is the mandatory data retention period for audit logs in the production environment?",
    "expected_behavior": "answer_grounded",
    "expected_answer": "Production audit logs must be retained for 365 days in tamper-proof immutable storage.",
    "expected_sources": ["sec-audit-101"],
    "contexts": [
      "[sec-audit-101] Audit logs in production environments must be retained for a mandatory duration of 365 days in tamper-proof immutable storage before archiving to cold storage."
    ]
  }
]
```
