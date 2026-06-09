# Cross-Connector Lineage (repository-driven)

Lineage is built from a connected **code repository of ETL/transform scripts**, and resolves
across **every connector** (Postgres, MySQL, MS SQL, BigQuery, Redshift, S3, …). Foreign-key
lineage from relational scans is folded into the same resolver.

## How it works (the chain)

```
ETL repo  ──parse──►  source→target references  ──resolve──►  catalog assets  ──►  lineage_edges
 (.sql/.py)   sqlglot / dbt / Airflow            qualified-name index (all connectors)     (+ confidence,
                                                                                            + script as transformation)
```

1. **Parse** (`connectors/etl/parsers.py`): each script becomes `{sources, targets}` edges.
   - SQL → sqlglot extracts `INSERT…SELECT` / `CREATE TABLE AS` / `MERGE` source & target tables
     (qualified, e.g. `shop.orders`, `project.dataset.table`).
   - dbt → `ref()` / `source()` dependencies.
   - Airflow → task deps + any embedded SQL.
2. **Resolve** (`services/lineage_service.py`): a qualified-name index over **all** assets'
   `external_id` + `name`. A reference is matched by the longest unambiguous suffix, with a
   **confidence score** (1.0 exact `db.schema.table` → 0.9 qualified → 0.7 unique name → 0.4
   ambiguous). This is why the same `orders` in Postgres vs BigQuery is not mis-linked.
3. **Persist**: an edge row in `lineage_edges` (source→target), with the script recorded as the
   transformation and the confidence stored.

FK lineage from a relational scan is stored on each table the same way and resolved by the same
engine, so the FK and script graphs merge into one.

## Connect an ETL repository

Add a **Source** of type `etl_repo` (or the legacy `github_etl`). Config (`repo_kind`):

| repo_kind | fields | use |
|-----------|--------|-----|
| `git` (default) | `git_url`, `branch`, `subpath`, `auth_token` | clone any Git URL (GitHub/GitLab/Bitbucket/self-hosted) |
| `github` | `github_token`, `repo_name`, `branch`, `subpath` | GitHub REST API (no clone) |
| `local` | `local_path`, `subpath` | read scripts from a local folder |

Then **Test → Scan**. The scripts are cataloged as `etl_pipeline` assets and their lineage is
resolved against everything currently in the catalog.

## Order doesn't matter — Rebuild

Lineage references are stored on the assets, so you can connect sources and the repo in any
order. The **Lineage page → "Rebuild Lineage"** button (or `POST /api/v1/lineage/rebuild`)
re-resolves every stored reference against the current catalog and (re)draws the graph. A scan
also triggers a rebuild automatically.

## Worked example

Script `etl/build_daily_orders.sql`:
```sql
INSERT INTO analytics.daily_orders
SELECT customer_id, SUM(total_amount) AS revenue
FROM shop.orders o JOIN shop.customers c ON c.id = o.customer_id
WHERE o.status = 'paid'
GROUP BY customer_id;
```
Produces edges: `shop.orders → analytics.daily_orders` and `shop.customers → analytics.daily_orders`,
each tagged with `build_daily_orders.sql` as the transformation — even if `orders`/`customers`
live in Postgres and `daily_orders` lives in BigQuery.

## Note on the "processed table in the same DB" case
A foreign key is **not** created by an ETL job, so FK introspection alone cannot see
`raw → processed` derivations. That derivation only exists in the transformation code — which is
exactly what this repository-driven path parses. Connect the repo and the raw→processed lineage
appears.
