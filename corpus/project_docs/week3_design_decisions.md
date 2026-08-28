# Design Decisions - Financial Data Warehouse on AWS
Architecture Decision Record (ADR) format: each entry states the decision, the context, and the trade-offs accepted.

## 1. Terraform over manual AWS console setup
**Decision:** Provision all infrastructure (S3, Lambda, EventBridge, IAM, CloudWatch, Budgets) via Terraform.
**Why:** Reproducible, version-controlled infrastructure that can be torn down completely (`make infra-down`) and rebuilt identically — critical for a portfolio project where guaranteeing zero ongoing cost between demos matters as much as the infra itself working.

## 2. Two independent serverless Lambdas, not one combined ingestion function
**Decision:** Separate Lambda functions for SEC EDGAR (fundamentals) and Alpha Vantage (prices).
**Why:** Different data shapes, different schedules, different rate-limit profiles, and independent failure domains — a failure pulling prices shouldn't block fundamentals ingestion, or vice versa. Same reasoning as Week 2's separate-Kafka-topics decision.

## 3. Local PostgreSQL via Docker instead of RDS/Redshift
**Decision:** Run the warehouse layer as local Postgres in Docker rather than a managed AWS database service.
**Why:** This project doesn't need managed HA or elastic scaling — RDS/Redshift would introduce ongoing cost risk against a deliberate $0 target, and would complicate the "tear down guarantees zero cost" property. Local Postgres also keeps this consistent with the same infra pattern used in Weeks 1 and 2.

## 4. dbt snapshots (SCD Type 2) for company classification tracking
**Decision:** Use dbt's built-in snapshot feature to track company SIC/sector reclassification over time, instead of overwriting current state.
**Why:** SCD Type 2 is a real, frequently-tested DE interview topic. dbt snapshots implement it without hand-rolled change-tracking logic, and the mechanism was verified with a real before/after test — manually updating one company's classification and re-running the snapshot, confirming the old row closed out and a new one opened correctly.

## 5. EventBridge Scheduler over a full orchestrator for ingestion triggers
**Decision:** Two simple daily-scheduled triggers via EventBridge Scheduler calling Lambdas directly, rather than a dedicated orchestration service (Airflow, Step Functions).
**Why:** Two independent tasks with no cross-task dependencies don't justify a full DAG orchestrator — EventBridge Scheduler is the AWS-native, zero-added-infrastructure choice for this scale.

## 6. Cost-guarded infrastructure by design, not added later
**Decision:** S3 lifecycle expiration, CloudWatch log retention limits, and an AWS Budget alert are provisioned alongside the pipeline itself.
**Why:** A portfolio project has no organizational cost oversight watching it — building guardrails in from day one, rather than "I'll add monitoring later," is the safer default and demonstrates real FinOps instinct, not just infrastructure literacy.

## 7. CI runs against real, scoped AWS credentials
**Decision:** GitHub Actions CI runs `terraform plan`, dbt parse-validation, pytest, and ruff against real (narrowly-scoped) AWS credentials, rather than mocking every AWS interaction.
**Why:** Catching genuine infrastructure drift (a `terraform plan` that doesn't match deployed state) is worth more than a fully-mocked pipeline blind to that entire bug class. Trade-off: real credentials live in CI secrets, mitigated by tight scoping and a plan-only (never apply) CI step.

## What I'd change at production scale
- Move from local Postgres to RDS or Redshift Serverless once concurrent/multi-user access is needed
- Replace EventBridge + direct Lambda invoke with Step Functions once workflows have real cross-task dependencies
- Add AWS Secrets Manager instead of `.env`-based credentials
- Separate dev/prod AWS accounts instead of a single account
