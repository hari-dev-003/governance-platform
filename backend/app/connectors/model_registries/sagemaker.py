"""AWS SageMaker model registry connector (lazy-imports boto3).

Discovers model package groups (-> ml_model), each group's model packages
(-> ml_model_version), and inference endpoints (-> ml_deployment).
"""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class SageMakerConnector(BaseConnector):
    def _client(self):
        import boto3
        c = self.config
        return boto3.client("sagemaker", aws_access_key_id=c.get("aws_access_key_id"),
                            aws_secret_access_key=c.get("aws_secret_access_key"),
                            region_name=c.get("region", "us-east-1"))

    async def test_connection(self) -> ConnectionTestResult:
        try:
            import boto3  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="boto3 not installed")
        try:
            self._client().list_model_package_groups(MaxResults=1)
            return ConnectionTestResult(success=True, message="Connected to SageMaker")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        assets: List[DiscoveredAsset] = []
        for page in client.get_paginator("list_model_package_groups").paginate():
            for g in page.get("ModelPackageGroupSummaryList", []):
                gname = g["ModelPackageGroupName"]
                gid = f"sagemaker://model-groups/{gname}"
                assets.append(DiscoveredAsset(
                    external_id=gid, name=gname, asset_type="ml_model",
                    metadata={"status": g.get("ModelPackageGroupStatus"),
                              "description": g.get("ModelPackageGroupDescription")}))
                # versions = model packages inside the group
                try:
                    for vp in client.get_paginator("list_model_packages").paginate(
                            ModelPackageGroupName=gname):
                        for p in vp.get("ModelPackageSummaryList", []):
                            ver = str(p.get("ModelPackageVersion") or "")
                            if not ver:
                                continue
                            assets.append(DiscoveredAsset(
                                external_id=f"{gid}/versions/{ver}", name=f"{gname} v{ver}",
                                asset_type="ml_model_version", parent_id=gid,
                                metadata={"version": ver,
                                          "stage": p.get("ModelApprovalStatus"),
                                          "status": p.get("ModelPackageStatus"),
                                          "arn": p.get("ModelPackageArn"),
                                          "run_details": {"metrics": {}, "params": {}}}))
                except Exception:  # noqa: BLE001
                    pass
        # production endpoints
        try:
            for page in client.get_paginator("list_endpoints").paginate():
                for ep in page.get("Endpoints", []):
                    assets.append(DiscoveredAsset(
                        external_id=f"sagemaker://endpoints/{ep['EndpointName']}",
                        name=ep["EndpointName"], asset_type="ml_deployment",
                        metadata={"status": ep.get("EndpointStatus")}))
        except Exception:  # noqa: BLE001
            pass
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
