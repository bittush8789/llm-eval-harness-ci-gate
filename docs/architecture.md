# 🏗️ System Architecture & Design

The **AI Evaluation & Regression Testing Platform** is structured into decoupled, modular layers separating target application logic, evaluation orchestration, persistence, API exposure, and CI/CD quality gate enforcement.

---

## 1. High-Level Architectural Diagram

```mermaid
graph TD
    subgraph Client_Interfaces ["Client & CI Interfaces"]
        GH["GitHub Actions CI/CD"]
        DEV["Developer CLI Scripts"]
        WEB["FastAPI Swagger UI / Clients"]
    end

    subgraph Core_Services ["Core Platform Services"]
        API["FastAPI Application (app.main)"]
        EVAL["Evaluation Engine (app.evaluation.evaluator)"]
        RAG["LangChain RAG Chain (app.chains.rag_chain)"]
        LOADER["Dataset Loader (app.evaluation.dataset_loader)"]
        DET["Deterministic Checker (app.evaluation.deterministic_checks)"]
        RAGAS["Ragas 0.2.x Engine (app.evaluation.ragas_metrics)"]
        COMP["Baseline Comparator (app.evaluation.baseline)"]
        GATE["Quality Gate Policy (app.evaluation.quality_gate)"]
        REP["Report Generator (app.evaluation.report_generator)"]
    end

    subgraph LLM_Orchestration ["LLM Model Orchestration"]
        APP_LLM["Target Application Model (Gemini 3.8 Flash / Mock)"]
        JUDGE_LLM["Evaluator Judge Model (Gemini 3.8 Pro / Mock)"]
    end

    subgraph Storage_Layer ["Persistence & File Storage"]
        PG[("PostgreSQL Database / SQLite Fallback")]
        FS_DATA["Versioned JSONL Datasets (datasets/v1/)"]
        FS_REPORTS["Markdown & JSON Reports (reports/)"]
        FS_LOCK["Baseline Lock (evaluation/baseline_lock.json)"]
    end

    GH --> DEV
    DEV --> EVAL
    WEB --> API
    API --> EVAL

    EVAL --> LOADER
    LOADER --> FS_DATA

    EVAL --> RAG
    RAG --> APP_LLM

    EVAL --> DET
    EVAL --> RAGAS
    RAGAS --> JUDGE_LLM

    EVAL --> COMP
    FS_LOCK --> COMP
    COMP --> GATE

    GATE --> REP
    REP --> FS_REPORTS

    EVAL --> PG
    GATE -->|Exit Code 0 / 1| GH
```

---

## 2. Subsystem Breakdown

### 2.1 Reference Application Layer (`app/chains/`, `app/prompts/`)
- **[RAGChain](file:///d:/harnesss/app/chains/rag_chain.py):** Orchestrates prompts, retrieval, model invocation, and response parsing.
- **System Prompt Decoupling:** Stored in [system_prompt.txt](file:///d:/harnesss/app/prompts/system_prompt.txt). Tracks prompt version and generates dynamic SHA256 hashes for regression detection.
- **Modular Retrieval:** Implements `BaseRetriever` and `SuppliedContextRetriever`, enabling future vector database plugins (e.g., Pinecone, Chroma, pgvector) without modifying evaluation interfaces.
- **Structured Outputs:** Uses Pydantic to ensure predictable outputs containing:
  - `question`: User query.
  - `answer`: Grounded response text.
  - `source_identifiers`: Document tokens (e.g. `['sec-audit-101']`).
  - `citation_metadata`: Source ID and snippet mappings.
  - `is_refusal`: Explicit boolean indicating inability to answer from context.

### 2.2 Dual-Model Architecture (`app/services/llm_service.py`)
To prevent evaluator bias and conflicting generation settings, the platform separates the target application model from the evaluator judge model:

| Role | Default Model | Responsibility |
| :--- | :--- | :--- |
| **Application Model** | `gemini-3.8-flash` | Generates candidate answers grounded in context. |
| **Evaluator Judge Model** | `gemini-3.8-pro` | Independently scores Faithfulness, Relevancy, and Precision. |
| **Offline Mock Model** | `MockChatModel` | Deterministic simulation for local dev, offline tests, and CI. |

### 2.3 Evaluation & Quality Gate Pipeline
The evaluation cycle executes in 6 distinct steps:
1. **Dataset Loading:** Validates JSONL files in `datasets/<version>/` via [DatasetLoader](file:///d:/harnesss/app/evaluation/dataset_loader.py).
2. **Batch Inference:** Invokes the RAG chain on all test cases and records latency (`execution_time_ms`).
3. **Dual Metric Computation:**
   - **Deterministic:** Assertions on schema formatting, citation presence/validity, refusal compliance, and injection defense.
   - **Semantic (Ragas 0.2.x):** Computes Faithfulness, Answer Relevancy, and Context Precision.
4. **Baseline Regression Diffing:** Compares candidate results against a designated baseline run.
5. **Quality Gate Decision:** Compares actual metrics and regressions against [thresholds.yaml](file:///d:/harnesss/evaluation/thresholds.yaml).
6. **Persistence & Reporting:** Writes atomic records to PostgreSQL and renders Markdown and JSON reports.

---

## 3. Database Entity-Relationship (ER) Model

```mermaid
erDiagram
    dataset_versions ||--o{ test_cases : contains
    evaluation_runs ||--o{ evaluation_results : produces
    evaluation_runs ||--o{ evaluation_metrics : aggregates

    dataset_versions {
        int id PK
        string version_tag UK
        text description
        datetime created_at
    }

    test_cases {
        int id PK
        int dataset_version_id FK
        string case_id
        string category
        text question
        string expected_behavior
        text expected_answer
        json expected_sources
        json contexts
        datetime created_at
    }

    evaluation_runs {
        int id PK
        string run_id UK
        string dataset_version
        string prompt_version
        string prompt_hash
        string app_model
        string evaluator_model
        string status
        boolean passed_quality_gate
        string baseline_run_id
        string git_commit
        json regression_summary
        datetime created_at
        datetime completed_at
    }

    evaluation_results {
        int id PK
        string run_id FK
        string test_case_id
        text question
        text generated_answer
        json cited_sources
        boolean is_refusal
        boolean passed_deterministic
        json deterministic_details
        float ragas_faithfulness
        float ragas_answer_relevancy
        float ragas_context_precision
        float execution_time_ms
        text error_message
        datetime created_at
    }

    evaluation_metrics {
        int id PK
        string run_id FK
        string metric_name
        float score
        float threshold
        boolean passed
        datetime created_at
    }
```

---

## 4. Security & Isolation Design

1. **Zero Credential Leakage:** Reports never include API keys, internal credentials, or secret tokens.
2. **Offline-First CI:** Unit tests, integration tests, and schema validators run with zero network access and no external API keys required.
3. **Database Portability:** Automatically detects PostgreSQL; if the PostgreSQL driver (`psycopg2`) is unavailable in a local lightweight development environment, it falls back to SQLite without breaking operations.
4. **Least-Privilege Docker Execution:** Container runs as non-root user `appuser:appgroup` (UID/GID 1001).
