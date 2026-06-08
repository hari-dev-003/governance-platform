"""Google BigQuery connector (lazy-imports google-cloud-bigquery)."""
from __future__ import annotations

import json
from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class BigQueryConnector(BaseConnector):
    def _client(self):
        from google.cloud import bigquery
        from google.oauth2 import service_account
        c = self.config
        creds = service_account.Credentials.from_service_account_info(
            json.loads(c["service_account_json"]),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(project=c["project_id"], credentials=creds)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from google.cloud import bigquery  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="google-cloud-bigquery not installed")
        try:
            list(self._client().list_datasets(max_results=1))
            return ConnectionTestResult(success=True, message="Connected to BigQuery")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        pid = self.config["project_id"]
        assets: List[DiscoveredAsset] = []
        for ds in client.list_datasets():
            dref = client.get_dataset(ds.dataset_id)
            assets.append(DiscoveredAsset(external_id=f"{pid}.{ds.dataset_id}", name=ds.dataset_id,
                                          asset_type="dataset", parent_id=pid,
                                          metadata={"location": dref.location}))
            for t in client.list_tables(ds.dataset_id):
                tref = client.get_table(t)
                tid = f"{pid}.{ds.dataset_id}.{t.table_id}"
                assets.append(DiscoveredAsset(external_id=tid, name=t.table_id, asset_type="table",
                                              parent_id=f"{pid}.{ds.dataset_id}",
                                              metadata={"num_rows": tref.num_rows, "num_bytes": tref.num_bytes}))
                for f in tref.schema:
                    assets.append(DiscoveredAsset(external_id=f"{tid}.{f.name}", name=f.name,
                                                  asset_type="column", parent_id=tid,
                                                  metadata={"data_type": f.field_type, "mode": f.mode}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
