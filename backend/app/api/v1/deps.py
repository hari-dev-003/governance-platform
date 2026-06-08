"""Shared API dependencies."""
from __future__ import annotations

from app.core.security import get_current_user, require_roles

# Convenience role gates
admin_only = require_roles("admin")
admin_or_steward = require_roles("admin", "data_steward")
ai_governance = require_roles("admin", "ai_risk_officer")
