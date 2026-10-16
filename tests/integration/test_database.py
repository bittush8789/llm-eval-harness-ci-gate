"""Integration tests for SQLAlchemy database models and repository layer."""

from app.database.repository import EvaluationRepository


def test_repository_sync_dataset_version(db_session):
    """Verify repository registers dataset version and test cases."""
    repo = EvaluationRepository(db_session)
    test_cases_data = [
        {
            "id": "TC-01",
            "category": "normal",
            "question": "Sample question?",
            "expected_behavior": "answer_grounded",
            "expected_answer": "Sample answer",
            "expected_sources": ["doc-1"],
            "contexts": ["[doc-1] text"],
        }
    ]

    ver = repo.sync_dataset_version(
        version_tag="v_test_db",
        test_cases_data=test_cases_data,
        description="Test version",
    )
    assert ver.id is not None
    assert ver.version_tag == "v_test_db"
    assert len(ver.test_cases) == 1
    assert ver.test_cases[0].case_id == "TC-01"


def test_repository_create_run_and_save_results(db_session):
    """Verify repository stores run, results, metrics and avoids duplicates on retry."""
    repo = EvaluationRepository(db_session)

    run_id = "eval_run_test_001"
    run = repo.create_or_update_run(
        run_id=run_id,
        dataset_version="v1",
        prompt_version="v1.0.0",
        prompt_hash="hash123",
        app_model="mock-model",
        evaluator_model="mock-evaluator",
        passed_quality_gate=True,
    )
    assert run.run_id == run_id

    results_data = [
        {
            "test_case_id": "NORM-001",
            "question": "Question 1?",
            "generated_answer": "Answer 1",
            "cited_sources": ["sec-audit-101"],
            "is_refusal": False,
            "passed_deterministic": True,
            "deterministic_details": {"schema_validity": {"passed": True}},
            "ragas_faithfulness": 0.95,
            "ragas_answer_relevancy": 0.90,
            "ragas_context_precision": 0.85,
            "execution_time_ms": 12.5,
            "error_message": None,
        }
    ]

    metrics_data = [
        {
            "metric_name": "faithfulness",
            "score": 0.95,
            "threshold": 0.85,
            "passed": True,
        }
    ]

    repo.save_results_and_metrics(run_id, results_data, metrics_data)

    retrieved = repo.get_run(run_id)
    assert retrieved is not None
    assert len(retrieved.results) == 1
    assert retrieved.results[0].test_case_id == "NORM-001"
    assert len(retrieved.metrics) == 1
    assert retrieved.metrics[0].metric_name == "faithfulness"

    # Retry should replace without duplicating rows
    repo.save_results_and_metrics(run_id, results_data, metrics_data)
    retrieved_after = repo.get_run(run_id)
    assert len(retrieved_after.results) == 1
    assert len(retrieved_after.metrics) == 1
