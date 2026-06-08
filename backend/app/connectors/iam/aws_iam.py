"""AWS IAM connector (lazy-imports boto3)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class AWSIAMConnector(BaseConnector):
    def _client(self):
        import boto3
        c = self.config
        return boto3.client("iam", aws_access_key_id=c.get("aws_access_key_id"),
                            aws_secret_access_key=c.get("aws_secret_access_key"))

    async def test_connection(self) -> ConnectionTestResult:
        try:
            import boto3  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="boto3 not installed")
        try:
            self._client().list_users(MaxItems=1)
            return ConnectionTestResult(success=True, message="Connected to AWS IAM")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        assets: List[DiscoveredAsset] = []
        for u in client.get_paginator("list_users").paginate():
            for user in u["Users"]:
                assets.append(DiscoveredAsset(external_id=f"aws-iam://users/{user['UserName']}",
                                              name=user["UserName"], asset_type="iam_user",
                                              metadata={"arn": user["Arn"]}))
        for r in client.get_paginator("list_roles").paginate():
            for role in r["Roles"]:
                assets.append(DiscoveredAsset(external_id=f"aws-iam://roles/{role['RoleName']}",
                                              name=role["RoleName"], asset_type="iam_role",
                                              metadata={"arn": role["Arn"]}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
