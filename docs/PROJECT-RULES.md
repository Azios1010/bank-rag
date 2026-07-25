# Project Rules & Development Guidelines (PROJECT-RULES.md)

> **Product-scope precedence:** New work must follow
> [PRODUCT-SCOPE.md](PRODUCT-SCOPE.md). Agents that are irrelevant to the
> selected unsecured workflow must return `NOT_APPLICABLE` or be disabled by
> product configuration; their presence in the original architecture does not
> expand the v1 scope.

**Project:** Digital Expert Agents  
**Target Audience:** Developers & AI Coding Assistants  
**Enforcement:** Mandatory for all architectural design, code generation, and pull requests.

---

## 1. Strict Scope Adherence
*   **Adhere Strictly to `PRD.md`:** Do not propose, design, or implement any feature outside the defined MVP scope without explicit written approval from the project lead.
*   **No Unsolicited Expansion:** Avoid adding speculative features (e.g., live web scraping, direct core banking mutations, automated SMS/email alerts, or custom LLM fine-tuning pipelines).
*   **Focus on Core Value:** Prioritize operational reliability, strict multi-agent orchestration, RAG accuracy, and human verification workflows.

---

## 2. Multi-Agent Rules & Communication Architecture
*   **Single Central Orchestrator:** All workflows must be controlled by exactly one `Banking Orchestrator` (Deep Agent with task planning, task breakdown, and dynamic re-planning capabilities).
*   **Authorized Specialist Agents:** The system is restricted to the following domain-specialized agents:
    1.  `Customer Relationship Agent`
    2.  `Credit Agent`
    3.  `Risk Management Agent`
    4.  `Legal & Compliance Agent`
    5.  `Collateral Appraisal Agent`
    6.  `Banking Operations Agent`
*   **Quality Gate / Debate Agent:** A `Reviewer Agent` must inspect specialist outputs on the Shared Board (`tìm lỗi sai`), conduct adversarial checks, and trigger iteration loops before synthesis.
*   **No Direct Point-to-Point Messaging:** Specialist agents must **not** send unstructured ad-hoc messages to one another directly.
*   **Shared Case State (`Shared Board`):** All agent communication must flow through a centralized, persistent `Shared Board` state using strongly typed JSON/Pydantic schemas.

### Concrete Typed State Example (Pydantic / TypeScript Schema Enforcement)
```python
# All sub-agents must read/write via strictly typed SharedBoard updates
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal

class AgentCitation(BaseModel):
    document_name: str
    page_number: int
    section_id: str
    quote: str

class SpecialistAssessment(BaseModel):
    agent_id: Literal["CustomerRelationship", "Credit", "RiskManagement", "LegalCompliance", "CollateralAppraisal"]
    status: Literal["PENDING", "SUCCESS", "REQUIRES_MORE_DATA", "ERROR"]
    key_findings: Dict[str, any]
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[AgentCitation] = Field(default_factory=list)
```

---

## 3. Execution Rules & Human-in-the-Loop Safeguards
*   **No Autonomous Write Actions:** All state-mutating actions (e.g., generating final contracts, scheduling onboarding, updating official case status to `APPROVED`/`REJECTED`) strictly require **Human Verification** via the Next.js frontend UI.
*   **Banking Operations Agent Boundaries:** The `Banking Operations Agent` operates **only after human sign-off** or during controlled pre-checks. Its permission scope is strictly restricted to:
    *   Updating case status (`PENDING_REVIEW` $\rightarrow$ `APPROVED`).
    *   Creating missing-document requests (`INCOMPLETE` $\rightarrow$ `AWAITING_DOCS`).
    *   Submitting prepared assessment drafts for human review.
    *   Interacting exclusively with **Mock SHB APIs** (never production endpoints).
*   **Mandatory Audit Logging:** Every agent execution step, Shared Board update, debate round, and operational API call must log an immutable audit record to the `audit_logs` table with full request/response payloads (`payload_trace`).

---

## 4. AI & Data Rules (RAG & Privacy)
*   **Policy-Driven Conclusions via RAG:** Every regulatory, credit threshold, or compliance conclusion must be supported by an explicit RAG citation (`AgentCitation`) from indexed internal banking policies.
*   **Accepted MVP Retrieval:** Policy retrieval must follow
    [RAG-ARCHITECTURE.md](RAG-ARCHITECTURE.md): hard metadata/version filters,
    full-text plus vector candidate generation, RRF merge, reranking, and a
    typed EvidencePack.
*   **HyDE Boundary:** Hypothetical text may only be used as evaluated query
    expansion. It must never be stored or displayed as policy evidence.
*   **Graph Boundary:** Full GraphRAG is outside the MVP. Policy relationships
    must be verified metadata, not unreviewed LLM-generated legal facts.
*   **No Guessing (`Zero-Hallucination Policy`):** If required data is missing from the uploaded documents (e.g., missing 2025 cash flow statement or unclear LTV appraisal), the agent **must not guess or impute** values. It must return status `INCOMPLETE` or `MANUAL_REVIEW` to the Shared Board and request the specific document.
*   **Customer Data Isolation:** Each loan application (`case_id`) must have strictly isolated document storage and vector query filtering.
*   **No Long-Term Memory Storage:** Customer Personally Identifiable Information (PII) and financial data must not be written to long-term LLM memory or vector indices. Only anonymized internal banking guidelines reside in `pgvector`.

---

## 5. Coding Standards & Architectural Separation
*   **Modular & Typed Code:**
    *   All TypeScript code (`/frontend`) must use strict typing (`tsconfig.json` with `"strict": true`). No `any` types allowed.
    *   All Python code (`/backend`) must use type hints and Pydantic v2 validation.
*   **Strict Layer Separation:** Never mix concerns. Maintain crisp boundaries across:
    *   **UI Layer (`/frontend`):** Next.js components, state hooks, and presentation logic only.
    *   **API Gateway (`/backend/app/api`):** FastAPI route controllers, request validation, and HTTP response formatting.
    *   **Orchestration & Agents (`/backend/app/agents`):** LangGraph state graphs, Deep Agent prompts, and Shared Board mechanics.
    *   **Tools & RAG (`/backend/app/services`):** Isolated tool wrappers, document chunking, and pgvector embeddings.
    *   **Storage (`/backend/app/db`):** SQLAlchemy/SQLModel models, migrations, and database session handling.
*   **Testability:** Every tool wrapper and agent calculation module (e.g., DSCR formula, KYC check) must be accompanied by unit tests using deterministic mocks without calling live LLM endpoints.

---

## 6. Communication Style (AI Coding Assistant Protocol)
*   **Conciseness First:** Keep explanations, commit messages, and chat responses brief, structured, and to the point.
*   **Minimal Diff Outputs:** When modifying existing files, output only the changed code blocks (`diff` / replacement chunks) unless the user explicitly requests the full file.
*   **Direct Action:** Prioritize executing valid tool calls directly rather than asking unnecessary conversational follow-ups when instructions are unambiguous.
