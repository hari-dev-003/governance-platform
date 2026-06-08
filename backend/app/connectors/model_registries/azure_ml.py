"""Azure ML model registry connector (lazy-imports azure-ai-ml)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class AzureMLConnector(BaseConnector):
    def _client(self):
        from azure.ai.ml import MLClient
        from azure.identity import ClientSecretCredential
        c = self.config
        cred = ClientSecretCredential(c["tenant_id"], c["client_id"], c["client_secret"])
        return MLClient(cred, c["subscription_id"], c["resource_group"], c["workspace_name"])

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from azure.ai.ml import MLClient  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="azure-ai-ml not installed")
        try:
            list(self._client().models.list())
            return ConnectionTestResult(success=True, message="Connected to Azure ML")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        assets: List[DiscoveredAsset] = []
        for m in client.models.list():
            assets.append(DiscoveredAsset(external_id=f"azureml://models/{m.name}", name=m.name,
                                          asset_type="ml_model", metadata={"latest_version": m.latest_version}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
