"""
Grafana Annotation Service
Creates annotations in Grafana dashboards for diagnostic results
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .client import GrafanaClient
from ..models.diagnostic import DiagnosticReport
from ..models.alarm import Alarm

logger = logging.getLogger(__name__)


class AnnotationService:
    """
    Flexible annotation service for Grafana
    Creates annotations with diagnostic information
    """

    def __init__(self, grafana_client: GrafanaClient):
        """
        Initialize annotation service

        Args:
            grafana_client: Grafana API client
        """
        self.client = grafana_client

    def create_diagnostic_annotation(
        self,
        alarm: Alarm,
        diagnostic_report: DiagnosticReport,
        dashboard_id: Optional[int] = None,
        panel_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create annotation for diagnostic report

        Args:
            alarm: Alarm object
            diagnostic_report: Diagnostic report
            dashboard_id: Optional dashboard ID
            panel_id: Optional panel ID
            tags: Optional tags

        Returns:
            Created annotation data
        """
        # Build annotation text (Markdown format)
        annotation_text = self._build_annotation_text(alarm, diagnostic_report)

        # Build tags
        annotation_tags = tags or []
        annotation_tags.extend([
            "diagnostic",
            f"alarm-{alarm.alarm_type}",
            f"severity-{alarm.severity.value.lower()}",
            f"risk-{diagnostic_report.risk_level.value.lower()}",
        ])

        # Convert timestamp to milliseconds
        timestamp_ms = int(alarm.timestamp.timestamp() * 1000)

        try:
            annotation = self.client.create_annotation(
                text=annotation_text,
                tags=annotation_tags,
                dashboard_id=dashboard_id,
                panel_id=panel_id,
                time_start=timestamp_ms,
            )
            logger.info(f"Created annotation for alarm {alarm.alarm_id}")
            return annotation
        except Exception as e:
            logger.error(f"Failed to create annotation: {e}", exc_info=True)
            raise

    async def create_diagnostic_annotation_async(
        self,
        alarm: Alarm,
        diagnostic_report: DiagnosticReport,
        dashboard_id: Optional[int] = None,
        panel_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create annotation asynchronously"""
        annotation_text = self._build_annotation_text(alarm, diagnostic_report)

        annotation_tags = tags or []
        annotation_tags.extend([
            "diagnostic",
            f"alarm-{alarm.alarm_type}",
            f"severity-{alarm.severity.value.lower()}",
            f"risk-{diagnostic_report.risk_level.value.lower()}",
        ])

        timestamp_ms = int(alarm.timestamp.timestamp() * 1000)

        try:
            annotation = await self.client.create_annotation_async(
                text=annotation_text,
                tags=annotation_tags,
                dashboard_id=dashboard_id,
                panel_id=panel_id,
                time_start=timestamp_ms,
            )
            logger.info(f"Created annotation for alarm {alarm.alarm_id}")
            return annotation
        except Exception as e:
            logger.error(f"Failed to create annotation: {e}", exc_info=True)
            raise

    def _build_annotation_text(self, alarm: Alarm, diagnostic_report: DiagnosticReport) -> str:
        """Build annotation text from diagnostic report"""
        # Use Markdown format for rich display
        lines = [
            f"## 🔍 Diagnostic Report: {alarm.alarm_type}",
            "",
            f"**Risk Level**: {diagnostic_report.risk_level.value}",
            f"**Severity**: {alarm.severity.value}",
            "",
            f"**Status**: {diagnostic_report.current_status}",
            "",
        ]

        if diagnostic_report.possible_causes:
            lines.append("**Possible Causes:**")
            for i, cause in enumerate(diagnostic_report.possible_causes[:3], 1):
                lines.append(f"{i}. {cause}")
            lines.append("")

        if diagnostic_report.recommended_actions:
            lines.append("**Recommended Actions:**")
            for i, action in enumerate(diagnostic_report.recommended_actions[:3], 1):
                lines.append(f"{i}. {action}")
            lines.append("")

        if diagnostic_report.references:
            lines.append("**References:**")
            for ref in diagnostic_report.references:
                lines.append(f"- {ref}")

        return "\n".join(lines)

    def get_annotations_for_alarm(
        self,
        alarm_id: str,
        dashboard_id: Optional[int] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get annotations for a specific alarm

        Args:
            alarm_id: Alarm ID
            dashboard_id: Optional dashboard ID filter
            from_time: Optional start time
            to_time: Optional end time

        Returns:
            List of annotations
        """
        tags = [f"alarm-{alarm_id}"]
        from_ms = int(from_time.timestamp() * 1000) if from_time else None
        to_ms = int(to_time.timestamp() * 1000) if to_time else None

        return self.client.get_annotations(
            dashboard_id=dashboard_id,
            from_time=from_ms,
            to_time=to_ms,
            tags=tags,
        )


