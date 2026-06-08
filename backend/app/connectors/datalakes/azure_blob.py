"""Azure Blob Storage connector (lazy-imports azure-storage-blob)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class AzureBlobConnector(BaseConnector):
    def _client(self):
        from azure.storage.blob import BlobServiceClient
        c = self.config
        if c.get("auth_method", "connection_string") == "connection_string":
            return BlobServiceClient.from_connection_string(c["connection_string"])
        from azure.identity import ClientSecretCredential
        cred = ClientSecretCredential(c["tenant_id"], c["client_id"], c["client_secret"])
        return BlobServiceClient(f"https://{c['account_name']}.blob.core.windows.net", credential=cred)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from azure.storage.blob import BlobServiceClient  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="azure-storage-blob not installed")
        try:
            list(self._client().list_containers(results_per_page=1).by_page().next())
            return ConnectionTestResult(success=True, message="Connected to Azure Blob Storage")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        client = self._client()
        assets: List[DiscoveredAsset] = []
        for container in client.list_containers():
            cname = container["name"]
            assets.append(DiscoveredAsset(external_id=f"azure://{cname}", name=cname, asset_type="container"))
            cc = client.get_container_client(cname)
            for blob in cc.list_blobs():
                ext = blob.name.split(".")[-1].lower()
                assets.append(DiscoveredAsset(
                    external_id=f"azure://{cname}/{blob.name}", name=blob.name.split("/")[-1],
                    asset_type="blob", parent_id=f"azure://{cname}",
                    metadata={"size_bytes": blob.size, "last_modified": str(blob.last_modified),
                              "file_format": ext}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
