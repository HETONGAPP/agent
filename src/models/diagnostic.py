"""
Diagnostic report model
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class RiskLevel(str, Enum):
    """Risk level"""

    LOW = "Low"  # Low risk
    MEDIUM = "Medium"  # Medium risk
    HIGH = "High"  # High risk


@dataclass
class DiagnosticReport:
    """Diagnostic report model"""

    alarm_id: str
    current_status: str  # Current status description
    risk_level: RiskLevel  # Risk level
    possible_causes: List[str] = field(default_factory=list)  # Possible causes
    recommended_actions: List[str] = field(default_factory=list)  # Recommended actions
    references: List[str] = field(default_factory=list)  # References
    generated_at: datetime = field(default_factory=datetime.now)
    markdown: str = ""  # Full Markdown format report

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "alarm_id": self.alarm_id,
            "current_status": self.current_status,
            "risk_level": self.risk_level.value,
            "possible_causes": self.possible_causes,
            "recommended_actions": self.recommended_actions,
            "references": self.references,
            "generated_at": self.generated_at.isoformat(),
            "markdown": self.markdown,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosticReport":
        """Create from dictionary"""
        from datetime import datetime

        return cls(
            alarm_id=data["alarm_id"],
            current_status=data["current_status"],
            risk_level=RiskLevel(data["risk_level"]),
            possible_causes=data.get("possible_causes", []),
            recommended_actions=data.get("recommended_actions", []),
            references=data.get("references", []),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            markdown=data.get("markdown", ""),
        )
