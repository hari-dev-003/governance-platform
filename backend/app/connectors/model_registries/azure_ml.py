"""Azure ML model registry connector (lazy-imports azure-ai-ml).

Discovers registered models (-> ml_model) and each model's versions
(-> ml_model_version) from an Azure ML workspace.
"""
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
            mid = f"azureml://models/{m.name}"
            assets.append(DiscoveredAsset(
                external_id=mid, name=m.name, asset_type="ml_model",
                metadata={"latest_version": getattr(m, "latest_version", None),
                          "description": getattr(m, "description", None)}))
            # all versions of this model
            try:
                for v in client.models.list(name=m.name):
                    ver = str(getattr(v, "version", "") or "")
                    if not ver:
                        continue
                    assets.append(DiscoveredAsset(
                        external_id=f"{mid}/versions/{ver}", name=f"{m.name} v{ver}",
                        asset_type="ml_model_version", parent_id=mid,
                        metadata={"version": ver,
                                  "stage": getattr(v, "stage", None) or "development",
                                  "tags": dict(getattr(v, "tags", {}) or {}),
                                  "run_details": {"metrics": {},
                                                  "params": dict(getattr(v, "properties", {}) or {})}}))
            except Exception:  # noqa: BLE001
                pass
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
