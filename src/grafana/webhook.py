"""
Grafana Webhook Handler
Processes Grafana alert webhook payloads
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class GrafanaWebhookHandler:
    """
    Flexible Grafana webhook handler
    Parses Grafana alert webhook payloads and extracts alarm information
    """

    def __init__(self):
        """Initialize webhook handler"""
        pass

    def parse_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Grafana webhook payload

        Args:
            payload: Grafana webhook payload

        Returns:
            Parsed alarm data dictionary
        """
        try:
            # Grafana webhook format (various versions)
            # Check for different payload structures
            if "alerts" in payload:
                # Grafana 8+ format
                alerts = payload.get("alerts", [])
                if alerts:
                    alert = alerts[0]  # Process first alert
                    return self._parse_alert_v8(alert, payload)
            elif "alert" in payload:
                # Older Grafana format
                return self._parse_alert_legacy(payload)
            elif "state" in payload:
                # Simple alert format
                return self._parse_simple_alert(payload)
            else:
                # Unknown format, try to extract common fields
                logger.warning(f"Unknown webhook format: {payload.keys()}")
                return self._parse_generic(payload)

        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}", exc_info=True)
            return self._create_fallback_alarm(payload)

    def _parse_alert_v8(self, alert: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Grafana 8+ alert format"""
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        values = alert.get("values", {})

        # Extract alarm information
        alarm_type = labels.get("alertname", labels.get("alarm_type", "unknown"))
        severity = self._extract_severity(labels, annotations)
        timestamp = self._parse_timestamp(alert.get("startsAt") or alert.get("time"))

        # Extract metric values
        metric_data = {}
        if values:
            metric_data.update(values)
        elif "value" in alert:
            metric_data["value"] = alert["value"]

        # Extract device information from labels
        device_id = labels.get("device_id") or labels.get("instance") or "unknown"
        device_type = labels.get("device_type") or labels.get("job", "").upper()
        site_id = labels.get("site_id") or labels.get("site", "")

        return {
            "alarm_type": alarm_type,
            "severity": severity,
            "timestamp": timestamp,
            "device_id": device_id,
            "device_type": device_type,
            "site_id": site_id,
            "labels": labels,
            "annotations": annotations,
            "metric_data": metric_data,
            "raw_alert": alert,
            "raw_payload": payload,
        }

    def _parse_alert_legacy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse legacy Grafana alert format"""
        alert = payload.get("alert", {})
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        alarm_type = labels.get("alertname", "unknown")
        severity = self._extract_severity(labels, annotations)
        timestamp = self._parse_timestamp(alert.get("startsAt"))

        return {
            "alarm_type": alarm_type,
            "severity": severity,
            "timestamp": timestamp,
            "device_id": labels.get("instance", "unknown"),
            "device_type": labels.get("job", "").upper(),
            "site_id": labels.get("site_id", ""),
            "labels": labels,
            "annotations": annotations,
            "metric_data": {},
            "raw_payload": payload,
        }

    def _parse_simple_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse simple alert format"""
        return {
            "alarm_type": payload.get("alertname", payload.get("alarm_type", "unknown")),
            "severity": self._extract_severity(payload, payload),
            "timestamp": self._parse_timestamp(payload.get("time")),
            "device_id": payload.get("device_id", payload.get("instance", "unknown")),
            "device_type": payload.get("device_type", ""),
            "site_id": payload.get("site_id", ""),
            "labels": payload.get("labels", {}),
            "annotations": payload.get("annotations", {}),
            "metric_data": payload.get("metric_data", {}),
            "raw_payload": payload,
        }

    def _parse_generic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse generic payload format"""
        return {
            "alarm_type": payload.get("alarm_type", payload.get("alertname", "unknown")),
            "severity": self._extract_severity(payload, payload),
            "timestamp": self._parse_timestamp(payload.get("timestamp") or payload.get("time")),
            "device_id": payload.get("device_id", payload.get("instance", "unknown")),
            "device_type": payload.get("device_type", ""),
            "site_id": payload.get("site_id", ""),
            "labels": payload.get("labels", {}),
            "annotations": payload.get("annotations", {}),
            "metric_data": payload.get("metric_data", payload.get("value", {})),
            "raw_payload": payload,
        }

    def _extract_severity(self, labels: Dict[str, Any], annotations: Dict[str, Any]) -> str:
        """Extract severity from labels or annotations"""
        # Try various severity fields
        severity = (
            labels.get("severity")
            or labels.get("level")
            or annotations.get("severity")
            or annotations.get("level")
            or "Warning"
        )

        # Normalize severity
        severity_upper = severity.upper()
        if severity_upper in ["CRITICAL", "CRIT", "ERROR", "FATAL"]:
            return "Critical"
        elif severity_upper in ["WARNING", "WARN"]:
            return "Warning"
        elif severity_upper in ["INFO", "INFORMATION"]:
            return "Info"
        else:
            return "Warning"  # Default

    def _parse_timestamp(self, timestamp: Optional[Any]) -> datetime:
        """Parse timestamp from various formats"""
        from datetime import UTC
        
        if timestamp is None:
            return datetime.now(UTC)

        if isinstance(timestamp, datetime):
            # Ensure timezone-aware
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=UTC)
            return timestamp

        if isinstance(timestamp, (int, float)):
            # Unix timestamp (seconds or milliseconds)
            if timestamp > 1e10:  # Milliseconds
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=UTC)

        # Try ISO format string
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            # Ensure timezone-aware
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except Exception:
            logger.warning(f"Failed to parse timestamp: {timestamp}")
            return datetime.now(UTC)

    def _create_fallback_alarm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback alarm when parsing fails"""
        from datetime import UTC
        return {
            "alarm_type": "unknown",
            "severity": "Warning",
            "timestamp": datetime.now(UTC),
            "device_id": "unknown",
            "device_type": "",
            "site_id": "",
            "labels": {},
            "annotations": {},
            "metric_data": {},
            "raw_payload": payload,
        }


