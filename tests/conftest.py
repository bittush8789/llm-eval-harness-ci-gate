import os
from typing import Generator

# Ensure tests run in offline test mode with isolated SQLite DB
os.environ["EVALUATION_OFFLINE_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "testing"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.chains.rag_chain import CitationItem, RAGChain, RAGResponse
from app.database.connection import get_db
from app.database.models import Base
from app.evaluation.dataset_loader import TestCaseSchema
from app.main import app
from app.services.llm_service import MockChatModel


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Ensure tests run in offline test mode with isolated SQLite DB."""
    monkeypatch.setenv("EVALUATION_OFFLINE_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ENVIRONMENT", "testing")


@pytest.fixture
def mock_llm() -> MockChatModel:
    """Fixture providing deterministic mock chat model."""
    return MockChatModel()


@pytest.fixture
def sample_test_case() -> TestCaseSchema:
    """Sample test case fixture."""
    return TestCaseSchema(
        id="NORM-001",
        question="What is the mandatory data retention period for audit logs?",
        contexts=["[sec-audit-101] Audit logs in production environments must be retained for 365 days."],
        expected_answer="Production audit logs must be retained for 365 days.",
        expected_behavior="answer_grounded",
        expected_sources=["sec-audit-101"],
        category="normal",
        dataset_version="v1",
    )


@pytest.fixture
def sample_unanswerable_case() -> TestCaseSchema:
    """Sample unanswerable test case fixture."""
    return TestCaseSchema(
        id="UNANS-001",
        question="What is the planned enterprise price for fiscal year 2027?",
        contexts=["[fin-pricing-101] The enterprise subscription rate for fiscal year 2024 is $45."],
        expected_answer="I am unable to answer this question based on the provided context.",
        expected_behavior="refusal",
        expected_sources=[],
        category="unanswerable",
        dataset_version="v1",
    )


@pytest.fixture
def sample_rag_response() -> RAGResponse:
    """Sample valid grounded RAGResponse."""
    return RAGResponse(
        question="What is the mandatory data retention period for audit logs?",
        answer="Production audit logs must be retained for 365 days [sec-audit-101].",
        source_identifiers=["sec-audit-101"],
        citation_metadata=[CitationItem(source_id="sec-audit-101")],
        prompt_version="v1.0.0",
        model_identifier="mock-chat-model",
        is_refusal=False,
    )


@pytest.fixture
def sample_refusal_response() -> RAGResponse:
    """Sample refusal RAGResponse."""
    return RAGResponse(
        question="What is the planned enterprise price for fiscal year 2027?",
        answer="I am unable to answer this question based on the provided context.",
        source_identifiers=[],
        citation_metadata=[],
        prompt_version="v1.0.0",
        model_identifier="mock-chat-model",
        is_refusal=True,
    )


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session using the application engine with all tables created."""
    from app.database.connection import init_db, SessionFactory
    init_db()
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient configured with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
