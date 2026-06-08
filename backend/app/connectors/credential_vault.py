"""Symmetric encryption of connection credentials (Fernet)."""
from __future__ import annotations

import json
from typing import Dict

from cryptography.fernet import Fernet

from app.core.config import settings


class CredentialVault:
    def __init__(self) -> None:
        self._fernet = Fernet(settings.fernet_key)

    def encrypt(self, credentials: Dict) -> str:
        return self._fernet.encrypt(json.dumps(credentials).encode()).decode()

    def decrypt(self, ciphertext: str) -> Dict:
        return json.loads(self._fernet.decrypt(ciphertext.encode()))


vault = CredentialVault()
