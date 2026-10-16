"""Integration tests for FastAPI evaluation endpoints."""

import pytest
from fastapi import status


def test_api_health_check(test_client):
    """Verify /health endpoint returns service and database status."""
    response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "version" in data
    assert "offline_mode" in data


def test_api_get_test_cases(test_client):
    """Verify /test-cases returns list of test cases for dataset version v1."""
    response = test_client.get("/test-cases?version=v1")
    assert response.status_code == status.HTTP_200_OK
    cases = response.json()
    assert len(cases) >= 20
    assert any(c["id"] == "NORM-001" for c in cases)


def test_api_evaluate_and_list_runs(test_client):
    """Verify /evaluate executes offline evaluation run and /evaluations lists it."""
    payload = {
        "dataset_version": "v1",
        "offline_mode": True,
        "prompt_version": "v1.0.0",
        "app_model": "mock-app-model",
        "evaluator_model": "mock-eval-model",
    }
    eval_resp = test_client.post("/evaluate", json=payload)
    assert eval_resp.status_code == status.HTTP_201_CREATED
    eval_data = eval_resp.json()
    run_id = eval_data["run_id"]
    assert eval_data["total_cases"] >= 20
    assert "faithfulness" in eval_data["metrics"]

    # Verify run is listed in /evaluations
    list_resp = test_client.get("/evaluations?limit=10")
    assert list_resp.status_code == status.HTTP_200_OK
    runs = list_resp.json()
    assert any(r["run_id"] == run_id for r in runs)

    # Verify run detail in /evaluations/{run_id}
    detail_resp = test_client.get(f"/evaluations/{run_id}")
    assert detail_resp.status_code == status.HTTP_200_OK
    detail_data = detail_resp.json()
    assert detail_data["run_id"] == run_id
    assert len(detail_data["results"]) >= 20
    assert len(detail_data["metrics"]) > 0

    # Verify report retrieval
    report_resp = test_client.get(f"/evaluations/{run_id}/report?format=markdown")
    assert report_resp.status_code == status.HTTP_200_OK
    assert "AI Evaluation & Regression Test Report" in report_resp.text
