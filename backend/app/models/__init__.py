"""ORM models.

Importing this package registers every table on ``Base.metadata``. The database
bootstrap and Alembic both rely on that, so any new model must be re-exported
here or it will be silently absent from migrations.
"""

from app.database.base import Base
from app.models.alert import Alert
from app.models.asset import Asset
from app.models.intelligence import (
    AnomalyResult,
    ApmResult,
    OeeAssetResult,
    OeeResult,
    PredictiveResult,
    PrescriptiveResult,
    PreventiveResult,
)
from app.models.maintenance import MaintenanceLog
from app.models.organization import AssetGroup, Location, Organization
from app.models.system import SystemSetting
from app.models.telemetry import Telemetry

__all__ = [
    "Alert",
    "AnomalyResult",
    "ApmResult",
    "Asset",
    "AssetGroup",
    "Base",
    "Location",
    "MaintenanceLog",
    "OeeAssetResult",
    "OeeResult",
    "Organization",
    "PredictiveResult",
    "PrescriptiveResult",
    "PreventiveResult",
    "SystemSetting",
    "Telemetry",
]
