# OpenLineage Ingestion — runtime lineage for any engine

For Spark (DataFrame **and** SQL), Airflow, Flink, dbt, Kafka Connect, etc., lineage is
captured **at runtime** (from the engine's execution plan) and pushed to this platform —
no code parsing, no OpenMetadata. Jobs emit standard OpenLineage events to:

```
POST  http://<host>:8000/api/v1/lineage/openlineage
```

If `OPENLINEAGE_API_KEY` is set in `backend/.env`, callers must send
`Authorization: Bearer <key>` (the OpenLineage HTTP transport's `api_key`).

The receiver maps each event's input/output datasets → `lineage_edges` (table level) and the
`columnLineage` facet → column-level edges, with the job as the transformation. Datasets not
yet in the catalog appear as lightweight external nodes. Edges show up immediately on the
**Lineage** page (Table / Column toggle) — no Rebuild needed.

---

## Spark (covers DataFrame API + SQL, with column lineage)

```bash
spark-submit \
  --packages io.openlineage:openlineage-spark_2.12:1.27.0 \
  --conf spark.extraListeners=io.openlineage.spark.agent.OpenLineageSparkListener \
  --conf spark.openlineage.transport.type=http \
  --conf spark.openlineage.transport.url=http://<host>:8000/api/v1 \
  --conf spark.openlineage.transport.endpoint=/lineage/openlineage \
  --conf spark.openlineage.transport.auth.type=api_key \
  --conf spark.openlineage.transport.auth.apiKey=<OPENLINEAGE_API_KEY> \
  --conf spark.openlineage.namespace=spark://etl-cluster \
  your_job.py
```
The listener reads Spark's logical plan, so `df.join(...).select(...).write...` emits real
input→output lineage including columns — even with no SQL.

## Airflow

```bash
pip install apache-airflow-providers-openlineage
```
`airflow.cfg`:
```ini
[openlineage]
transport = {"type": "http", "url": "http://<host>:8000/api/v1", "endpoint": "/lineage/openlineage", "auth": {"type": "api_key", "apiKey": "<OPENLINEAGE_API_KEY>"}}
namespace = airflow://prod
```

## dbt

```bash
pip install openlineage-dbt
OPENLINEAGE_URL=http://<host>:8000/api/v1 OPENLINEAGE_ENDPOINT=/lineage/openlineage \
OPENLINEAGE_API_KEY=<key> dbt-ol run
```

## Manual emit (raw Python / pandas / Kafka Streams — anything without an agent)

```python
from openlineage.client import OpenLineageClient
from openlineage.client.transport.http import HttpConfig, HttpTransport, ApiKeyTokenProvider
from openlineage.client.run import RunEvent, RunState, Run, Job, Dataset
from openlineage.client.facet import ColumnLineageDatasetFacet, ColumnLineageDatasetFacetFieldsAdditional as F, \
    ColumnLineageDatasetFacetFieldsAdditionalInputFields as In
import uuid, datetime

cfg = HttpConfig(url="http://<host>:8000/api/v1", endpoint="/lineage/openlineage",
                 auth=ApiKeyTokenProvider({"api_key": "<key>"}))
client = OpenLineageClient(transport=HttpTransport(cfg))

ns = "postgres://db:5432"
col = ColumnLineageDatasetFacet(fields={
    "revenue": F(inputFields=[In(namespace=ns, name="shop.orders", field="total_amount")]),
})
client.emit(RunEvent(
    eventType=RunState.COMPLETE, eventTime=datetime.datetime.now().isoformat(),
    run=Run(runId=str(uuid.uuid4())), job=Job(namespace="custom://etl", name="customer_revenue_job"),
    inputs=[Dataset(namespace=ns, name="shop.orders"), Dataset(namespace=ns, name="shop.customers")],
    outputs=[Dataset(namespace=ns, name="analytics.customer_revenue", facets={"columnLineage": col})],
))
```

---

## Dataset naming = how it links to your catalog

Use the dataset's **qualified name** (e.g. `shop.orders`, `database.schema.table`,
`project.dataset.table`) as the OpenLineage `name`. The resolver matches it to the cataloged
asset by longest qualified suffix (same engine used for script lineage), so OpenLineage edges
connect to the exact tables/columns already in your catalog. Unmatched datasets render as
external nodes.

## Quick test (no engine needed)

```bash
curl -X POST http://localhost:8000/api/v1/lineage/openlineage \
  -H "Content-Type: application/json" \
  -d '{"eventType":"COMPLETE","run":{"runId":"r1"},
       "job":{"namespace":"spark://etl","name":"customer_revenue_job"},
       "inputs":[{"namespace":"postgres://db","name":"shop.orders"},{"namespace":"postgres://db","name":"shop.customers"}],
       "outputs":[{"namespace":"postgres://db","name":"analytics.customer_revenue",
         "facets":{"columnLineage":{"fields":{
           "revenue":{"inputFields":[{"namespace":"postgres://db","name":"shop.orders","field":"total_amount"}]}}}}}]}'
```
Then open the Lineage page → you'll see `shop.orders → analytics.customer_revenue` (Table) and
`shop.orders.total_amount → analytics.customer_revenue.revenue` (Column).
