# Digital Expert Agents — MVP

Multi-agent credit assessment MVP for corporate banking. A LangGraph orchestrator coordinates five specialist agents, a reviewer/debate loop, a human approval gate, and post-approval operations. Policy knowledge is retrieved from per-agent pgvector knowledge bases; customer case documents remain isolated from durable policy memory.

The first product slice is **SME unsecured working-capital loan
pre-screening**. Read the [product documentation](docs/README.md) before
adding new workflows or policy data.

The accepted MVP retrieval design is documented in
[RAG architecture](docs/RAG-ARCHITECTURE.md), with the implementation order in
the [MVP delivery plan](docs/MVP-DELIVERY-PLAN.md).

## Run the real-agent demo

1. Revoke any API key that has been pasted into chat or source control, then create a fresh key.
2. Copy `.env.example` to `.env` and set `LLM_API_KEY` there. Never commit `.env`.
3. Start the stack:

   ```bash
   docker compose up --build
   ```

4. Open `http://localhost:3000`. The bootstrap process uploads and embeds `backend/resources/policies/QD-HHB-2026-01.txt`, then creates a demo case with a fictional dossier ready to assess.

The case workspace now contains a live Agent Control Center. Assessment requests return immediately while the LLM agents run in the backend. The page receives operational events over SSE, updates each specialist result as soon as it is posted, and visualizes Reviewer → Specialist challenges. “Dừng an toàn” finishes the current provider call and pauses at the next durable PostgreSQL checkpoint; “Tiếp tục từ checkpoint” resumes without rerunning completed specialists.

If you already have an older Minh An demo stopped in `TIER1_PLANNING` or `TIER2_DEBATING`, use “Khôi phục phiên thẩm định”. On the next `docker compose up --build`, Alembic automatically adds the runtime/checkpoint tables before the API starts.

The default runtime uses the FPT AI Marketplace OpenAI-compatible endpoint, `GLM-5.2` for structured agent calls, and `Vietnamese_Embedding` for RAG. It fails closed when a model call fails; deterministic embeddings are accepted only when `ENVIRONMENT=test`.

## Local verification

```bash
.venv/bin/python -m pytest backend/tests -q
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

The demo uses header authentication and mock core-banking endpoints. Set `AUTH_MODE=jwt`, disable mock APIs, and configure issuer/JWKS values before deploying outside development.
