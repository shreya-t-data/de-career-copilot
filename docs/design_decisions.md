# Design Decisions — DE Career Copilot

Architecture Decision Record (ADR) format: each entry states the decision, the context, and the trade-offs accepted.

## 1. Databricks Free Edition over a self-hosted vector database
**Decision:** Use Databricks Free Edition (Unity Catalog, Vector Search, Lakebase) rather than a self-hosted stack (e.g. Postgres + pgvector on a local Docker container).
**Why:** Free Edition provides a governed, production-shaped lakehouse platform — the same one many DE job postings now list — at genuinely $0 cost, with real constraints (serverless-only compute, no persistent guarantee) that are worth learning to design around rather than avoid.

## 2. Local embeddings (sentence-transformers) over Databricks Foundation Model APIs
**Decision:** Run `all-MiniLM-L6-v2` locally on serverless CPU rather than call Databricks' hosted embedding endpoints.
**Why:** Foundation Model APIs bill per token — small for this corpus, but not $0. Running an open-source model directly keeps the entire project's cost exactly zero. Same reasoning as VADER-over-LLM in the Week 2 streaming project: match the tool to the actual requirement, not the most powerful available option.

## 3. Local MCP server over a hosted one
**Decision:** Run the MCP server as a local process on my own machine, packaged as a Desktop Extension, rather than deploy it remotely.
**Why:** Appropriate for a single-user tool with no need for external access. Packaging as a `.mcpb` bundle (Anthropic's current Desktop Extension format) gave one-click install/update without needing to hand-maintain a JSON config file — the platform's own tooling moved to this model during this project's build, which itself became a real lesson in not assuming documentation patterns stay static.

## 4. Deterministic keyword matching for skills-gap checking, not another LLM call
**Decision:** `get_skills_gap` uses plain string matching against a fixed skill list, rather than asking an LLM to assess skill overlap.
**Why:** This is a factual lookup, not a judgment call — fast, free, fully explainable, and testable without mocking an LLM. Observed directly during testing: Claude Desktop still layered its own reasoning on top of the tool's output (catching JD-specific requirements like "Unity Catalog" or "MBI Clearance" that the fixed skill list didn't cover) — confirming the intended division of labor: the tool handles what's checkable, Claude handles what requires judgment.

## 5. Lakebase over a plain Delta table for the application tracker
**Decision:** Use Lakebase (Databricks' Postgres-compatible OLTP service) for `job_applications`, rather than a Delta table.
**Why:** This table needs frequent, low-latency single-row writes and updates (as applications are logged and their status changes) — an OLTP-shaped workload, not the append-heavy/batch pattern Delta Lake is optimized for.

## 6. Fresh connections per Lakebase call, not one long-lived connection
**Decision:** Each write tool opens and closes its own Postgres connection, rather than holding one connection open for the server's lifetime.
**Why:** Lakebase force-closes idle connections after 24 hours, and this MCP server may sit unused for days between sessions. A connection held from startup would eventually go stale; opening fresh per call costs almost nothing and avoids the failure mode entirely.

## 7. Environment-panel dependencies over inline %pip install + restartPython()
**Decision:** Declare notebook dependencies via Databricks' serverless Environment side panel, rather than `%pip install` followed by `dbutils.library.restartPython()` mid-notebook.
**Why:** Discovered directly during Day 6: a scheduled Job repeatedly failed with `ModuleNotFoundError` despite the exact same install-then-restart pattern working fine when run interactively, cell by cell. The likely cause was a race condition between "Run All" advancing to the next cell and the Python restart actually completing. Declaring dependencies upfront removes the restart — and the race condition — entirely, and is also the pattern Databricks documents as intended for reproducible, job-safe execution.

## Real bugs caught during this build (worth naming honestly)
- **Silent primary-key bug**: an early Vector Search index was created with `chunk_index` (not unique across files) as its primary key, silently collapsing 11 rows into 2. Caught by noticing `indexed_row_count` didn't match the source table's row count — not by an error message.
- **Copy-pasted URL bug**: the Databricks host URL in `.env` included a `/browse?o=...` path fragment copied directly from a browser tab, causing every API request to silently redirect to a login page rather than fail with an obvious auth error. Diagnosed by testing the raw HTTP request outside the SDK, rather than assuming the token was wrong.
- **Stale in-memory state**: several `NameError`/`ModuleNotFoundError` issues traced back to Databricks' `dbutils.library.restartPython()` wiping all session variables — a pattern that repeated until fully understood, at which point it stopped costing debugging time.
- **Duplicate/misplaced source files**: a naive `cp` command with a shared destination filename silently overwrote one project's design-decisions doc with another's during initial corpus assembly — caught by noticing two output files were byte-identical, not by any tool warning.

## What I'd change at production/multi-user scale
- Service-principal authentication instead of a personal access token and personal Lakebase role
- A hosted (not local) MCP server, if this needed to be used from more than one machine
- A more robust chunking strategy (e.g. respecting markdown heading structure explicitly) as the corpus grows beyond a handful of documents
- Automated corpus ingestion (e.g. a GitHub webhook triggering the Lakeflow Job) instead of manual file upload
