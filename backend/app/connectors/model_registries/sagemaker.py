"""AWS SageMaker model registry connector (lazy-imports boto3)."""
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
            for g in page["ModelPackageGroupSummaryList"]:
                gid = f"sagemaker://model-groups/{g['ModelPackageGroupName']}"
                assets.append(DiscoveredAsset(external_id=gid, name=g["ModelPackageGroupName"],
                                              asset_type="ml_model",
                                              metadata={"status": g["ModelPackageGroupStatus"]}))
        for page in client.get_paginator("list_endpoints").paginate():
            for ep in page["Endpoints"]:
                assets.append(DiscoveredAsset(external_id=f"sagemaker://endpoints/{ep['EndpointName']}",
                                              name=ep["EndpointName"], asset_type="ml_deployment",
                                              metadata={"status": ep["EndpointStatus"]}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
