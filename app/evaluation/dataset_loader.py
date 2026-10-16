"""Dataset loader with Pydantic validation for versioned evaluation JSONL datasets."""

import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError
from app.core.logging import logger


class TestCaseSchema(BaseModel):
    """Pydantic validation schema for an individual evaluation test case."""

    __test__ = False
    id: str = Field(..., min_length=1, description="Unique identifier (e.g., NORM-001)")
    question: str = Field(..., min_length=3, description="User query or test question")
    contexts: List[str] = Field(default_factory=list, description="List of grounding context passages")
    expected_answer: str = Field(..., description="Reference answer or refusal statement")
    expected_behavior: str = Field(
        ...,
        description="Expected behavior: answer_grounded, refusal, reject_prompt_injection, cite_sources",
    )
    expected_sources: List[str] = Field(
        default_factory=list,
        description="List of expected document identifiers (e.g. ['sec-audit-101'])",
    )
    category: str = Field(
        ...,
        description="Category: normal, edge_case, unanswerable, adversarial, citation",
    )
    dataset_version: str = Field(..., description="Dataset version tag (e.g. 'v1')")


class DatasetLoader:
    """Loads and validates JSONL evaluation datasets from the filesystem."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # Workspace root datasets/
            self.base_dir = Path(__file__).resolve().parent.parent.parent / "datasets"

    def load_version(self, version: str = "v1") -> List[TestCaseSchema]:
        """Load and validate all JSONL files within the specified dataset version directory."""
        version_dir = self.base_dir / version
        if not version_dir.is_dir():
            raise FileNotFoundError(f"Dataset version directory not found: {version_dir}")

        jsonl_files = sorted(version_dir.glob("*.jsonl"))
        if not jsonl_files:
            raise FileNotFoundError(f"No .jsonl files found in {version_dir}")

        test_cases: List[TestCaseSchema] = []
        errors: List[str] = []

        for file_path in jsonl_files:
            logger.info(f"Loading dataset file: {file_path.name}")
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line_str = line.strip()
                    if not line_str or line_str.startswith("#"):
                        continue
                    try:
                        data = json.loads(line_str)
                        test_case = TestCaseSchema(**data)
                        test_cases.append(test_case)
                    except json.JSONDecodeError as jde:
                        msg = f"JSON decode error in {file_path.name}:{line_num}: {jde}"
                        logger.error(msg)
                        errors.append(msg)
                    except ValidationError as ve:
                        msg = f"Schema validation error in {file_path.name}:{line_num}: {ve}"
                        logger.error(msg)
                        errors.append(msg)

        if errors:
            raise ValueError(f"Encountered {len(errors)} errors loading dataset {version}:\n" + "\n".join(errors))

        # Check unique IDs
        seen_ids = set()
        duplicates = set()
        for tc in test_cases:
            if tc.id in seen_ids:
                duplicates.add(tc.id)
            seen_ids.add(tc.id)

        if duplicates:
            raise ValueError(f"Duplicate test case IDs found in dataset {version}: {duplicates}")

        logger.info(f"Successfully loaded {len(test_cases)} validated test cases from version '{version}'.")
        return test_cases
