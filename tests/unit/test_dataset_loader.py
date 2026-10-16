"""Unit tests for dataset loading and Pydantic validation."""

import json
from pathlib import Path
import pytest
from app.evaluation.dataset_loader import DatasetLoader, TestCaseSchema


def test_load_v1_datasets_success():
    """Verify standard v1 dataset directory loads all valid test cases."""
    loader = DatasetLoader()
    cases = loader.load_version("v1")

    assert len(cases) >= 20
    categories = {c.category for c in cases}
    expected_categories = {"normal", "edge_case", "unanswerable", "adversarial", "citation"}
    assert expected_categories.issubset(categories)

    # Verify field types
    for c in cases:
        assert isinstance(c.id, str) and len(c.id) > 0
        assert isinstance(c.question, str) and len(c.question) > 3
        assert isinstance(c.contexts, list)
        assert isinstance(c.expected_sources, list)
        assert c.dataset_version == "v1"


def test_dataset_loader_nonexistent_version(tmp_path):
    """Verify loading non-existent version raises FileNotFoundError."""
    loader = DatasetLoader(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        loader.load_version("non_existent_version_999")


def test_dataset_loader_malformed_json(tmp_path):
    """Verify malformed JSON syntax raises ValueError with file and line details."""
    ver_dir = tmp_path / "v_test"
    ver_dir.mkdir(parents=True)
    bad_file = ver_dir / "bad.jsonl"
    bad_file.write_text("{\"id\": \"TEST-01\", question missing quotes: bad}\n", encoding="utf-8")

    loader = DatasetLoader(base_dir=str(tmp_path))
    with pytest.raises(ValueError, match="JSON decode error"):
        loader.load_version("v_test")


def test_dataset_loader_schema_validation_failure(tmp_path):
    """Verify missing required fields triggers Pydantic validation error."""
    ver_dir = tmp_path / "v_test2"
    ver_dir.mkdir(parents=True)
    bad_schema = ver_dir / "invalid_schema.jsonl"
    # Missing 'question' and 'expected_behavior'
    bad_schema.write_text(json.dumps({"id": "TC-1", "category": "normal"}) + "\n", encoding="utf-8")

    loader = DatasetLoader(base_dir=str(tmp_path))
    with pytest.raises(ValueError, match="Schema validation error"):
        loader.load_version("v_test2")


def test_dataset_loader_duplicate_ids(tmp_path):
    """Verify duplicate test case IDs across files trigger an error."""
    ver_dir = tmp_path / "v_dup"
    ver_dir.mkdir(parents=True)
    valid_tc = {
        "id": "DUP-001",
        "question": "Sample question?",
        "contexts": ["[doc-1] text"],
        "expected_answer": "ans",
        "expected_behavior": "answer_grounded",
        "expected_sources": ["doc-1"],
        "category": "normal",
        "dataset_version": "v_dup",
    }
    f1 = ver_dir / "f1.jsonl"
    f2 = ver_dir / "f2.jsonl"
    f1.write_text(json.dumps(valid_tc) + "\n", encoding="utf-8")
    f2.write_text(json.dumps(valid_tc) + "\n", encoding="utf-8")

    loader = DatasetLoader(base_dir=str(tmp_path))
    with pytest.raises(ValueError, match="Duplicate test case IDs"):
        loader.load_version("v_dup")
