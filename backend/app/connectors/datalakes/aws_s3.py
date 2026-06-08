"""AWS S3 data-lake connector (lazy-imports boto3 + pandas)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class AWSS3Connector(BaseConnector):
    def _client(self):
        import boto3
        c = self.config
        return boto3.client(
            "s3",
            aws_access_key_id=c.get("aws_access_key_id"),
            aws_secret_access_key=c.get("aws_secret_access_key"),
            region_name=c.get("region", "us-east-1"),
        )

    async def test_connection(self) -> ConnectionTestResult:
        try:
            import boto3  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="boto3 not installed")
        try:
            self._client().list_buckets()
            return ConnectionTestResult(success=True, message="Connected to AWS S3")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    def _infer_schema(self, client, bucket: str, key: str) -> list:
        import io
        import pandas as pd
        obj = client.get_object(Bucket=bucket, Key=key, Range="bytes=0-1048576")
        content = obj["Body"].read()
        if key.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(content))
        elif key.endswith(".csv"):
            df = pd.read_csv(io.StringIO(content.decode("utf-8", "ignore")), nrows=5)
        elif key.endswith(".json"):
            df = pd.read_json(io.StringIO(content.decode("utf-8", "ignore")), lines=True, nrows=5)
        else:
            return []
        return [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns]

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        assets: List[DiscoveredAsset] = []
        targets = self.config.get("buckets")
        buckets = [{"Name": b} for b in targets] if targets else client.list_buckets()["Buckets"]
        for b in buckets:
            name = b["Name"]
            assets.append(DiscoveredAsset(external_id=f"s3://{name}", name=name, asset_type="bucket"))
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=name):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    ext = key.split(".")[-1].lower()
                    cols = []
                    if ext in ("parquet", "csv", "json"):
                        try:
                            cols = self._infer_schema(client, name, key)
                        except Exception:  # noqa: BLE001
                            pass
                    assets.append(DiscoveredAsset(
                        external_id=f"s3://{name}/{key}", name=key.split("/")[-1],
                        asset_type="file", parent_id=f"s3://{name}",
                        metadata={"size_bytes": obj["Size"], "last_modified": str(obj["LastModified"]),
                                  "file_format": ext, "columns": cols}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
