"""Import every ORM model so SQLAlchemy's metadata is fully populated."""
from app.models.identity import Organization, User  # noqa: F401
from app.models.sources import DataSource  # noqa: F401
from app.models.assets import Asset  # noqa: F401
from app.models.lineage import LineageEdge  # noqa: F401
from app.models.classification import ClassificationRule, ClassificationResult, ClassificationRun  # noqa: F401
from app.models.quality import (  # noqa: F401
    QualityRule, QualityCheckRun, QualityCheckResult,
)
from app.models.policies import AccessRequest  # noqa: F401
from app.models.ai_models import AIModel, AIModelVersion  # noqa: F401
from app.models.risk import RiskAssessment  # noqa: F401
from app.models.bias import BiasTestRun  # noqa: F401
from app.models.monitoring import MonitoringConfig, DriftAlert  # noqa: F401
from app.models.compliance import (  # noqa: F401
    ComplianceFramework, ComplianceRequirement, ComplianceMapping,
)
from app.models.audit import AuditLog  # noqa: F401

__all__ = [
    "Organization", "User", "DataSource", "Asset", "LineageEdge",
    "ClassificationRule", "ClassificationResult", "ClassificationRun",
    "QualityRule", "QualityCheckRun", "QualityCheckResult", "AccessRequest", "AIModel", "AIModelVersion", "RiskAssessment", "BiasTestRun",
    "MonitoringConfig", "DriftAlert", "ComplianceFramework", "ComplianceRequirement",
    "ComplianceMapping", "AuditLog",
]
