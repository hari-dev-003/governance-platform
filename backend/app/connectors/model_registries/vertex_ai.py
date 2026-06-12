"""Google Vertex AI model registry connector (lazy-imports google-cloud-aiplatform).

Discovers registered models (-> ml_model) and each model's registry versions
(-> ml_model_version) from a Vertex AI project/location.
"""
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
            mid = f"vertex://models/{m.resource_name}"
            assets.append(DiscoveredAsset(
                external_id=mid, name=m.display_name, asset_type="ml_model",
                metadata={"version_id": getattr(m, "version_id", None),
                          "resource_name": m.resource_name}))
            # registry versions for this model
            try:
                registry = ai.models.ModelRegistry(model=m.resource_name)
                for v in registry.list_versions():
                    ver = str(getattr(v, "version_id", "") or "")
                    if not ver:
                        continue
                    aliases = list(getattr(v, "version_aliases", []) or [])
                    assets.append(DiscoveredAsset(
                        external_id=f"{mid}/versions/{ver}", name=f"{m.display_name} v{ver}",
                        asset_type="ml_model_version", parent_id=mid,
                        metadata={"version": ver,
                                  "stage": (aliases[0] if aliases else "development"),
                                  "aliases": aliases,
                                  "run_details": {"metrics": {}, "params": {}}}))
            except Exception:  # noqa: BLE001
                pass
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
