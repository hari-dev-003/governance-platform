"""Keycloak IAM connector (lazy-imports python-keycloak)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class KeycloakConnector(BaseConnector):
    def _admin(self):
        from keycloak import KeycloakAdmin
        c = self.config
        return KeycloakAdmin(server_url=c["server_url"], realm_name=c["realm"],
                             username=c["admin_username"], password=c["admin_password"], verify=True)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            from keycloak import KeycloakAdmin  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="python-keycloak not installed")
        try:
            self._admin().get_realm(self.config["realm"])
            return ConnectionTestResult(success=True, message="Connected to Keycloak")
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        admin = self._admin()
        realm = self.config["realm"]
        assets: List[DiscoveredAsset] = []
        for u in admin.get_users():
            assets.append(DiscoveredAsset(external_id=f"keycloak://{realm}/users/{u['id']}",
                                          name=u.get("username", ""), asset_type="iam_user",
                                          parent_id=f"keycloak://{realm}",
                                          metadata={"email": u.get("email"), "enabled": u.get("enabled")}))
        for r in admin.get_realm_roles():
            assets.append(DiscoveredAsset(external_id=f"keycloak://{realm}/roles/{r['id']}",
                                          name=r["name"], asset_type="iam_role",
                                          parent_id=f"keycloak://{realm}"))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
