"""MLflow model registry connector (lazy-imports mlflow)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class MLflowConnector(BaseConnector):
    def _client(self):
        from mlflow.tracking import MlflowClient
        return MlflowClient(tracking_uri=self.config["tracking_uri"])

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from mlflow.tracking import MlflowClient  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="mlflow not installed")
        try:
            self._client().search_experiments(max_results=1)
            return ConnectionTestResult(success=True, message="Connected to MLflow")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        assets: List[DiscoveredAsset] = []
        for m in client.search_registered_models():
            mid = f"mlflow://models/{m.name}"
            assets.append(DiscoveredAsset(external_id=mid, name=m.name, asset_type="ml_model",
                                          metadata={"description": m.description, "tags": dict(m.tags)}))
            for v in client.search_model_versions(f"name='{m.name}'"):
                run_data = {}
                if v.run_id:
                    try:
                        run = client.get_run(v.run_id)
                        run_data = {"metrics": dict(run.data.metrics), "params": dict(run.data.params)}
                    except Exception:  # noqa: BLE001
                        pass
                assets.append(DiscoveredAsset(
                    external_id=f"{mid}/versions/{v.version}", name=f"{m.name} v{v.version}",
                    asset_type="ml_model_version", parent_id=mid,
                    metadata={"version": v.version, "stage": v.current_stage, "run_id": v.run_id,
                              "run_details": run_data}))
        for exp in client.search_experiments():
            assets.append(DiscoveredAsset(external_id=f"mlflow://experiments/{exp.experiment_id}",
                                          name=exp.name, asset_type="ml_experiment",
                                          metadata={"lifecycle_stage": exp.lifecycle_stage}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
