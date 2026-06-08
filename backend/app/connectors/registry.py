"""Connector registry — maps a ConnectorType to its implementation.

Implementations are resolved lazily by dotted path so that the core app boots
even when optional connector libraries (boto3, azure-*, google-cloud-*, mlflow,
python-keycloak, aioodbc, ...) are not installed. The relevant ImportError is
only raised when that specific connector is actually used.
"""
from __future__ import annotations

import importlib
from typing import Dict, Tuple

from app.connectors.base import BaseConnector, ConnectorType

# ConnectorType -> ("module.path", "ClassName")
_REGISTRY: Dict[ConnectorType, Tuple[str, str]] = {
    ConnectorType.POSTGRESQL: ("app.connectors.databases.postgresql", "PostgreSQLConnector"),
    ConnectorType.MSSQL: ("app.connectors.databases.mssql", "MSSQLConnector"),
    ConnectorType.MYSQL: ("app.connectors.databases.mysql", "MySQLConnector"),
    ConnectorType.AWS_S3: ("app.connectors.datalakes.aws_s3", "AWSS3Connector"),
    ConnectorType.AZURE_BLOB: ("app.connectors.datalakes.azure_blob", "AzureBlobConnector"),
    ConnectorType.BIGQUERY: ("app.connectors.warehouses.bigquery", "BigQueryConnector"),
    ConnectorType.REDSHIFT: ("app.connectors.warehouses.redshift", "RedshiftConnector"),
    ConnectorType.GITHUB_ETL: ("app.connectors.etl.github_etl", "GitHubETLConnector"),
    ConnectorType.MLFLOW: ("app.connectors.model_registries.mlflow_connector", "MLflowConnector"),
    ConnectorType.SAGEMAKER: ("app.connectors.model_registries.sagemaker", "SageMakerConnector"),
    ConnectorType.AZURE_ML: ("app.connectors.model_registries.azure_ml", "AzureMLConnector"),
    ConnectorType.VERTEX_AI: ("app.connectors.model_registries.vertex_ai", "VertexAIConnector"),
    ConnectorType.AWS_IAM: ("app.connectors.iam.aws_iam", "AWSIAMConnector"),
    ConnectorType.KEYCLOAK: ("app.connectors.iam.keycloak_connector", "KeycloakConnector"),
}


def list_connector_types() -> list[str]:
    return [ct.value for ct in _REGISTRY]


def get_connector(connector_type: ConnectorType, config: dict) -> BaseConnector:
    entry = _REGISTRY.get(connector_type)
    if not entry:
        raise ValueError(f"No connector registered for type: {connector_type}")
    module_path, class_name = entry
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(config)
