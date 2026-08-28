# Design Decisions — E-Commerce Analytics Pipeline

## ADR 1: dbt over raw SQL scripts for transformation

**Decision:** Use dbt to manage all transformation logic (staging + marts), rather than writing plain SQL scripts run manually or via Python.

**Why:** dbt gives version-controlled, testable, documented SQL with automatic dependency resolution — if `dim_customers` depends on `fct_orders`, dbt figures that out from the `ref()` calls and builds them in the correct order. Raw SQL scripts would require manually managing execution order and offer no built-in testing framework.

**Trade-off:** Adds a tool and a learning curve. For a one-off analysis, plain SQL would be faster to write. For a maintained pipeline, dbt's structure pays for itself quickly.

---

## ADR 2: Layered modeling — raw → staging → marts

**Decision:** Three explicit layers: an untouched `raw` landing zone, thin 1:1 `staging` views, and business-ready `marts` tables.

**Why:** Separating "clean the data" (staging) from "model it for a business question" (marts) means a renamed source column only needs fixing in one staging model, not in every downstream query. It also means marts can be freely reshaped for new analytics questions without touching ingestion logic.

**Trade-off:** More files and more indirection than querying raw tables directly. Worth it once more than one person or one dashboard depends on the data — for a single throwaway query, it's overhead.

---

## ADR 3: PostgreSQL over a dedicated cloud warehouse

**Decision:** Use containerized PostgreSQL for both the raw landing zone and analytics marts, rather than Snowflake, BigQuery, or Redshift.

**Why:** At ~100K rows, this dataset doesn't need distributed/columnar warehouse performance. Postgres is free, runs entirely locally via Docker, and requires no cloud account or billing setup — appropriate for a learning project at this scale.

**Trade-off:** Postgres won't demonstrate warehouse-specific skills (e.g., BigQuery partitioning, Snowflake's micro-partitions). The dbt modeling logic itself is largely portable to a real warehouse if this pipeline needed to scale — swapping the connection profile is a bigger lift than rewriting the SQL.

---

## ADR 4: Idempotent, full-refresh ingestion (drop + reload)

**Decision:** The ingestion script drops and recreates each raw table on every run, rather than appending or upserting.

**Why:** Simplicity and correctness at this scale — a full reload guarantees the raw layer always matches the source CSVs exactly, with no risk of duplicate or stale rows from a partial previous run. This also makes the pipeline safe to re-run after a failure without manual cleanup.

**Trade-off:** Doesn't scale to large or frequently-updated datasets — a full reload of a multi-million-row table on every run would be slow and wasteful. At production scale, this would move to incremental loading (only new/changed rows) using dbt's incremental materialization or CDC (change data capture).

---

## ADR 5: Apache Airflow for orchestration

**Decision:** Use Airflow to sequence ingestion → dbt run → dbt test, rather than a shell script or cron job.

**Why:** Airflow gives visibility (UI showing task status/history/logs), retry logic, and explicit dependency management — if `load_raw_data` fails, `dbt_run` never starts. A shell script could technically do the same steps, but gives you none of that observability, and it's the orchestrator most commonly asked about in DE interviews.

**Trade-off:** Airflow has real operational overhead — its own metadata database, multiple long-running services, and (as this project's build log shows) real dependency-conflict risk with other tools in the same environment. For a pipeline this small, a simpler scheduler would technically suffice; Airflow is the choice that matches what larger teams actually run in production.

---

## What I'd change at production scale

- **Incremental dbt models** instead of full rebuilds, once data volume grows past what a full reload can handle quickly
- **CI (GitHub Actions)** running `dbt test` on every pull request, catching bad SQL before merge rather than at manual run time
- **Scheduled DAG runs** instead of manual triggers, once the pipeline needs to reflect a live/updating data source
- **Alerting on task failure** (Slack/email), so pipeline breaks are noticed immediately rather than at the next manual check
- **A dedicated cloud warehouse** if data volume or concurrent query load outgrew what a single Postgres instance can handle