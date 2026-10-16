# 📚 AI Evaluation & Regression Testing Platform - Documentation

Welcome to the comprehensive documentation for the **AI Evaluation & Regression Testing Platform**.

This platform provides enterprise-grade quality assurance for Large Language Model (LLM) and Retrieval-Augmented Generation (RAG) applications, preventing silent quality degradation, hallucinations, citation dropouts, and safety vulnerabilities during prompt and model updates.

---

## 🧭 Documentation Structure

```text
docs/
├── index.md                        # Documentation Home & Quick Navigation (This file)
├── architecture.md                 # System Architecture, Components & Data Flow
├── api_reference.md                # Complete REST API Reference & Request/Response Models
├── evaluation_and_metrics.md       # Ragas 0.2.x, Deterministic Assertions, Quality Gates
├── dataset_guide.md                # Dataset Schema, 5 Test Categories & Authoring Guide
├── deployment_and_ci.md            # Docker, PostgreSQL, Alembic & GitHub Actions CI/CD
├── aws_ec2_deployment.md           # Step-by-Step AWS EC2 Production Deployment
└── runbook_and_troubleshooting.md  # Operator Runbook, Triage Guide & Failure Handling
```

---

## ⚡ Quick Navigation

| Document | Description |
| :--- | :--- |
| **[System Architecture](file:///d:/harnesss/docs/architecture.md)** | Modular design, LangChain integration, dual-model configuration, PostgreSQL storage model, and Mermaid flow diagrams. |
| **[API Reference](file:///d:/harnesss/docs/api_reference.md)** | Endpoints (`/health`, `/evaluate`, `/evaluations`, `/test-cases`), payload structures, status codes, and `curl` commands. |
| **[Metrics & Quality Gates](file:///d:/harnesss/docs/evaluation_and_metrics.md)** | Explanation of Faithfulness, Answer Relevancy, Context Precision, deterministic assertions, and `thresholds.yaml` policy. |
| **[Dataset & Authoring Guide](file:///d:/harnesss/docs/dataset_guide.md)** | JSONL format, Pydantic schema validation, writing normal, edge, unanswerable, adversarial, and citation test cases. |
| **[Deployment & CI/CD](file:///d:/harnesss/docs/deployment_and_ci.md)** | Multi-stage Dockerfile, Docker Compose stack, database migrations with Alembic, GitHub Actions CI workflow, and LangSmith. |
| **[AWS EC2 Deployment Guide](file:///d:/harnesss/docs/aws_ec2_deployment.md)** | Complete guide to launching on AWS EC2 with Docker Compose, Nginx reverse proxy, and free SSL via Certbot. |
| **[Runbook & Troubleshooting](file:///d:/harnesss/docs/runbook_and_troubleshooting.md)** | How to triage CI failures, resolve metric drops, update locked baselines, and debug offline/online execution issues. |

---

## 🚀 30-Second Quick Start

### 1. Run Complete Offline Test Suite
```powershell
python -m pytest tests/ -v
```

### 2. Lock an Initial Reference Baseline
```powershell
python -m scripts.initialize_baseline --dataset-version v1 --offline
```

### 3. Run Evaluation & Enforce Quality Gates
```powershell
python -m scripts.run_evaluation --dataset-version v1 --offline
```

### 4. Compare Candidate Run with Baseline
```powershell
python -m scripts.compare_runs --candidate <cand_run_id> --baseline <base_run_id> --format markdown
```
