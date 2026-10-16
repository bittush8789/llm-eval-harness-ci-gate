# 📁 Dataset Specification & Authoring Guide

The evaluation platform relies on versioned JSONL evaluation datasets stored under the `datasets/` directory.

---

## 1. Directory Structure

Datasets are isolated by version directories to guarantee immutable benchmark tracking:

```text
datasets/
└── v1/
    ├── normal_questions.jsonl        # 5 cases: Standard factual grounded Q&A
    ├── edge_cases.jsonl             # 4 cases: Complex boundaries, acronyms, multi-source
    ├── unanswerable_questions.jsonl    # 4 cases: Out-of-corpus queries requiring refusal
    ├── adversarial_prompts.jsonl    # 4 cases: Prompt injection, jailbreak & leak resistance
    └── citation_cases.jsonl         # 4 cases: Multi-document synthesis & exact citations
```

---

## 2. Test Case Schema (`TestCaseSchema`)

Every line in a `.jsonl` file must be a standalone JSON object adhering to the following Pydantic schema:

```python
class TestCaseSchema(BaseModel):
    id: str = Field(..., min_length=1, description="Unique identifier (e.g., NORM-001)")
    question: str = Field(..., min_length=3, description="User query or test prompt")
    contexts: List[str] = Field(default_factory=list, description="Grounding passages")
    expected_answer: str = Field(..., description="Reference answer or refusal statement")
    expected_behavior: str = Field(..., description="Behavioral classification")
    expected_sources: List[str] = Field(default_factory=list, description="Mandatory source tokens")
    category: str = Field(..., description="Test category")
    dataset_version: str = Field(..., description="Version tag (e.g. 'v1')")
```

### JSON Line Example
```json
{
  "id": "NORM-001",
  "question": "What is the mandatory data retention period for audit logs in the production environment?",
  "contexts": [
    "[sec-audit-101] Audit logs in production environments must be retained for a mandatory duration of 365 days in tamper-proof immutable storage before archiving to cold storage."
  ],
  "expected_answer": "Production audit logs must be retained for 365 days in tamper-proof immutable storage.",
  "expected_behavior": "answer_grounded",
  "expected_sources": ["sec-audit-101"],
  "category": "normal",
  "dataset_version": "v1"
}
```

---

## 3. The 5 Test Categories

### 3.1 Normal Questions (`normal`)
- **Purpose:** Verifies that everyday factual questions are answered correctly and grounded in context.
- **`expected_behavior`:** `answer_grounded`.
- **Expected Sources:** Exact document identifier tokens (e.g. `['sec-audit-101']`).

### 3.2 Edge Cases (`edge_case`)
- **Purpose:** Tests model performance under challenging query patterns:
  - Exact boundary thresholds (e.g., "files of exactly 100MB").
  - Deprecated vs active policy precedence (overriding legacy documentation).
  - Multi-condition logical rules (cross-region replication with customer keys).
  - Acronyms vs full titles (RBAC vs Role-Based Access Control).
- **`expected_behavior`:** `answer_grounded`.

### 3.3 Unanswerable Questions (`unanswerable`)
- **Purpose:** Verifies that the model **refuses** when context lacks the necessary facts, rather than hallucinating an answer.
- **`expected_behavior`:** `refusal`.
- **`expected_sources`:** Empty list `[]`.
- **`expected_answer`:** Standard refusal string (e.g., *"I am unable to answer this question based on the provided context."*).

### 3.4 Adversarial Prompts (`adversarial`)
- **Purpose:** Verifies safety and guardrail robustness against:
  - Direct instruction overrides (*"Ignore previous instructions..."*).
  - Jailbreaks and persona assumptions (*"You are DAN..."*).
  - System prompt leak attempts (*"Print your developer instructions..."*).
  - Indirect prompt injection embedded within context passages.
- **`expected_behavior`:** `reject_prompt_injection` or `refusal`.

### 3.5 Citation Cases (`citation`)
- **Purpose:** Verifies rigorous multi-source document synthesis.
- **`expected_behavior`:** `cite_sources`.
- **`expected_sources`:** Multiple required document tokens (e.g., `['sec-policy-402', 'iam-guide-101']`).

---

## 4. Best Practices for Adding Test Cases

1. **Semantic Grounding Over Exact String Matching:**
   Do not write tests that fail on harmless paraphrasing. The evaluation engine evaluates semantic equivalence and behavior, not character-by-character regexes.

2. **Always Use Tagged Context Passages:**
   Format all context passages with document identifiers at the beginning of each passage:
   ```text
   "[doc-id-123] The policy statement text goes here..."
   ```

3. **Validate Before Committing:**
   Run the dataset validator directly using Python to verify syntax and schema compliance:
   ```powershell
   python -c "from app.evaluation.dataset_loader import DatasetLoader; l = DatasetLoader(); cases = l.load_version('v1'); print(f'Validated {len(cases)} cases successfully!')"
   ```

4. **Creating a New Dataset Version (`v2`):**
   - Create directory `datasets/v2/`.
   - Copy or add new JSONL files setting `"dataset_version": "v2"` on each case.
   - Run evaluation targeting `v2`:
     ```powershell
     python -m scripts.run_evaluation --dataset-version v2
     ```
