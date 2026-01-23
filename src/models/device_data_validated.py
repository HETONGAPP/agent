"""
Validated Device Data Model
Enhanced version with Pydantic validation
"""

from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional


class DeviceType(str, Enum):
    """Device type enumeration"""

    BMS = "BMS"  # Battery Management System
    PCS = "PCS"  # Power Conversion System (includes Storage/PV/Generic inverters)
    UPS = "UPS"  # Uninterruptible Power Supply
    TMS = "TMS"  # Thermal Management System
    EMS = "EMS"  # Energy Management System
    TRANSFORMER = "TRANSFORMER"  # Transformer
    MONITORING = "MONITORING"  # Monitoring System
    OTHER = "OTHER"  # Other components


class DeviceDataValidated(BaseModel):
    """
    Validated Device Data Model
    Uses Pydantic for validation and type checking
    """

    device_id: str = Field(..., min_length=1, description="Device identifier")
    device_type: DeviceType = Field(..., description="Device type")
    timestamp: datetime = Field(..., description="Data timestamp (UTC)")
    source: str = Field(..., min_length=1, description="Data source identifier")
    site_id: Optional[str] = Field(None, description="Site ID for multi-site support")
    site_name: Optional[str] = Field(None, description="Site name for multi-site support")
    data: Dict[str, Any] = Field(default_factory=dict, description="Device data fields")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @validator("timestamp", pre=True)
    def validate_timestamp(cls, v):
        """Ensure timestamp is timezone-aware"""
        if v is None:
            return datetime.now(UTC)
        if isinstance(v, str):
            try:
                parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed
            except Exception:
                return datetime.now(UTC)
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v
        return datetime.now(UTC)

    @validator("device_type", pre=True)
    def validate_device_type(cls, v):
        """Validate device type"""
        if isinstance(v, str):
            try:
                return DeviceType(v.upper())
            except ValueError:
                return DeviceType.OTHER
        return v

    @root_validator
    def validate_data_fields(cls, values):
        """Validate data fields based on device type"""
        device_type = values.get("device_type")
        data = values.get("data", {})
        
        # Basic validation for common fields
        if device_type == DeviceType.BMS:
            # Validate BMS-specific fields if present
            if "soc" in data:
                soc = data["soc"]
                if isinstance(soc, (int, float)) and not (0 <= soc <= 100):
                    raise ValueError(f"SOC must be between 0 and 100, got {soc}")
            if "soh" in data:
                soh = data["soh"]
                if isinstance(soh, (int, float)) and not (0 <= soh <= 100):
                    raise ValueError(f"SOH must be between 0 and 100, got {soh}")
        
        return values

    def get_field(self, field_path: str, default: Any = None) -> Any:
        """
        Get field value using dot notation path
        Example: get_field('voltage.max') or get_field('temperature')
        """
        keys = field_path.split(".")
        value = self.data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def has_field(self, field_path: str) -> bool:
        """Check if field exists"""
        return self.get_field(field_path) is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
        }
        if self.site_id:
            result["site_id"] = self.site_id
        if self.site_name:
            result["site_name"] = self.site_name
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceDataValidated":
        """Create from dictionary"""
        return cls(**data)

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }












