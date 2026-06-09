"""Abstract base connector + shared data contracts.

Every external integration (database, lake, warehouse, ETL, model registry, IAM)
implements this one interface, so the core platform never needs to know the
specifics of any source.
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConnectorType(str, enum.Enum):
    # Databases
    POSTGRESQL = "postgresql"
    MSSQL = "mssql"
    MYSQL = "mysql"
    # Data Lakes
    AWS_S3 = "aws_s3"
    AZURE_BLOB = "azure_blob"
    # Warehouses
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    # ETL
    GITHUB_ETL = "github_etl"
    ETL_REPO = "etl_repo"
    # Model registries
    MLFLOW = "mlflow"
    SAGEMAKER = "sagemaker"
    AZURE_ML = "azure_ml"
    VERTEX_AI = "vertex_ai"
    # IAM
    AWS_IAM = "aws_iam"
    KEYCLOAK = "keycloak"


# Maps each connector type to the high-level category used in the catalog.
CONNECTOR_CATEGORY: Dict[ConnectorType, str] = {
    ConnectorType.POSTGRESQL: "database",
    ConnectorType.MSSQL: "database",
    ConnectorType.MYSQL: "database",
    ConnectorType.AWS_S3: "datalake",
    ConnectorType.AZURE_BLOB: "datalake",
    ConnectorType.BIGQUERY: "warehouse",
    ConnectorType.REDSHIFT: "warehouse",
    ConnectorType.GITHUB_ETL: "etl",
    ConnectorType.ETL_REPO: "etl",
    ConnectorType.MLFLOW: "model_registry",
    ConnectorType.SAGEMAKER: "model_registry",
    ConnectorType.AZURE_ML: "model_registry",
    ConnectorType.VERTEX_AI: "model_registry",
    ConnectorType.AWS_IAM: "iam",
    ConnectorType.KEYCLOAK: "iam",
}


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class DiscoveredAsset(BaseModel):
    external_id: str
    name: str
    asset_type: str
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    raw_lineage: Optional[List[Dict]] = None


class BaseConnector(ABC):
    """All connectors implement this contract."""

    def __init__(self, connection_config: Dict[str, Any]):
        self.config = connection_config

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Verify connectivity. Called when a user saves a connection."""

    @abstractmethod
    async def discover(self) -> List[DiscoveredAsset]:
        """Crawl the source and return every discovered asset."""

    @abstractmethod
    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        """Fetch detailed metadata for a single asset."""

    async def get_sample_data(self, external_id: str, limit: int = 10) -> List[Dict]:
        """Optional: sample rows for profiling. Default: not supported."""
        return []
