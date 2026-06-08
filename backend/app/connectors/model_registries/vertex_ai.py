"""Google Vertex AI model registry connector (lazy-imports google-cloud-aiplatform)."""
from __future__ import annotations

import json
from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class VertexAIConnector(BaseConnector):
    def _init(self):
        from google.cloud import aiplatform
        from google.oauth2 import service_account
        c = self.config
        creds = service_account.Credentials.from_service_account_info(json.loads(c["service_account_json"]))
        aiplatform.init(project=c["project_id"], location=c.get("location", "us-central1"), credentials=creds)
        return aiplatform

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from google.cloud import aiplatform  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="google-cloud-aiplatform not installed")
        try:
            self._init().Model.list()
            return ConnectionTestResult(success=True, message="Connected to Vertex AI")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        ai = self._init()
        assets: List[DiscoveredAsset] = []
        for m in ai.Model.list():
            assets.append(DiscoveredAsset(external_id=f"vertex://models/{m.resource_name}",
                                          name=m.display_name, asset_type="ml_model",
                                          metadata={"version_id": getattr(m, "version_id", None)}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
