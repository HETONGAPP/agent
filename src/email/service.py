"""
Email Service
Main service for sending alarm notification emails with diagnostic reports
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .client import EmailClient
from .template import EmailTemplateEngine
from ..models.alarm import Alarm
from ..models.diagnostic import DiagnosticReport

logger = logging.getLogger(__name__)


class EmailService:
    """
    Flexible email service
    Sends alarm notification emails with diagnostic reports
    """

    def __init__(
        self,
        email_client: EmailClient,
        template_engine: Optional[EmailTemplateEngine] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize email service

        Args:
            email_client: Email client instance
            template_engine: Optional template engine
            config: Service configuration
        """
        self.email_client = email_client
        self.config = config or {}
        self.template_engine = template_engine or EmailTemplateEngine()

        # Email configuration
        self.from_address = self.config.get("from_address", "agent@example.com")
        self.from_name = self.config.get("from_name", "BESS Agent")
        self.to_addresses = self.config.get("to_addresses", [])
        self.cc_addresses = self.config.get("cc_addresses", [])
        self.subject_template = self.config.get(
            "subject_template", "⚠️ BESS Alert – {alarm_type} ({severity})"
        )

    async def send_alarm_email(
        self,
        alarm: Alarm,
        diagnostic_report: Optional[DiagnosticReport] = None,
        device_data: Optional[Dict[str, Any]] = None,
        custom_recipients: Optional[List[str]] = None,
        custom_subject: Optional[str] = None,
    ) -> bool:
        """
        Send alarm notification email

        Args:
            alarm: Alarm object
            diagnostic_report: Optional diagnostic report
            device_data: Optional device data
            custom_recipients: Optional custom recipient list
            custom_subject: Optional custom subject

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Determine recipients
            recipients = custom_recipients or self._get_recipients_for_severity(alarm.severity.value)

            if not recipients:
                logger.warning(f"No recipients configured for severity {alarm.severity.value}")
                return False

            # Generate subject
            subject = custom_subject or self._generate_subject(alarm)

            # Generate email content
            html_content, text_content = self._generate_email_content(
                alarm, diagnostic_report, device_data
            )

            # Send email
            from_addr = f"{self.from_name} <{self.from_address}>"
            success = await self.email_client.send_async(
                from_address=from_addr,
                to_addresses=recipients,
                subject=subject,
                body_text=text_content,
                body_html=html_content,
                cc_addresses=self.cc_addresses if not custom_recipients else None,
            )

            if success:
                logger.info(f"Alarm email sent for {alarm.alarm_id} to {len(recipients)} recipient(s)")
            else:
                logger.error(f"Failed to send alarm email for {alarm.alarm_id}")

            return success

        except Exception as e:
            logger.error(f"Error sending alarm email: {e}", exc_info=True)
            return False

    def _get_recipients_for_severity(self, severity: str) -> List[str]:
        """
        Get recipient list based on alarm severity

        Args:
            severity: Alarm severity (Critical, Warning, Info)

        Returns:
            List of email addresses
        """
        # Check for severity-specific recipients in config
        severity_recipients = self.config.get("severity_recipients", {})
        if severity in severity_recipients:
            return severity_recipients[severity]

        # Fallback to default recipients
        return self.to_addresses

    def _generate_subject(self, alarm: Alarm) -> str:
        """Generate email subject"""
        return self.subject_template.format(
            alarm_type=alarm.alarm_type,
            severity=alarm.severity.value,
            alarm_id=alarm.alarm_id,
        )

    def _generate_email_content(
        self,
        alarm: Alarm,
        diagnostic_report: Optional[DiagnosticReport],
        device_data: Optional[Dict[str, Any]],
    ) -> tuple[str, str]:
        """
        Generate email content (HTML and text)

        Args:
            alarm: Alarm object
            diagnostic_report: Optional diagnostic report
            device_data: Optional device data

        Returns:
            Tuple of (html_content, text_content)
        """
        # Build context for template
        context = {
            "alarm": alarm.to_dict(),
            "alarm_id": alarm.alarm_id,
            "alarm_type": alarm.alarm_type,
            "severity": alarm.severity.value,
            "timestamp": alarm.timestamp.isoformat(),
            "diagnostic": diagnostic_report.to_dict() if diagnostic_report else None,
            "device_data": device_data or {},
            "grafana_url": self.config.get("grafana_url", "http://localhost:3000"),
        }

        # Try to render template
        template_name = self._get_template_name(alarm, diagnostic_report)
        try:
            html_content, text_content = self.template_engine.render(template_name, context)
            return html_content, text_content
        except Exception as e:
            logger.warning(f"Template rendering failed, using default: {e}")
            return self._generate_default_content(alarm, diagnostic_report, device_data)

    def _get_template_name(self, alarm: Alarm, diagnostic_report: Optional[DiagnosticReport]) -> str:
        """Get template name based on alarm and diagnostic"""
        if diagnostic_report:
            return "alarm_with_diagnostic"
        else:
            return "alarm_simple"

    def _generate_default_content(
        self,
        alarm: Alarm,
        diagnostic_report: Optional[DiagnosticReport],
        device_data: Optional[Dict[str, Any]],
    ) -> tuple[str, str]:
        """Generate default email content"""
        html_lines = [
            "<html><body>",
            f"<h2>⚠️ BESS Alarm Notification</h2>",
            f"<p><strong>Alarm ID:</strong> {alarm.alarm_id}</p>",
            f"<p><strong>Alarm Type:</strong> {alarm.alarm_type}</p>",
            f"<p><strong>Severity:</strong> {alarm.severity.value}</p>",
            f"<p><strong>Timestamp:</strong> {alarm.timestamp.isoformat()}</p>",
            f"<p><strong>Source:</strong> {alarm.source}</p>",
        ]

        if device_data:
            html_lines.append("<h3>Device Information</h3>")
            html_lines.append("<ul>")
            for key, value in list(device_data.items())[:10]:
                html_lines.append(f"<li><strong>{key}:</strong> {value}</li>")
            html_lines.append("</ul>")

        if diagnostic_report:
            html_lines.append("<h3>Diagnostic Report</h3>")
            html_lines.append(f"<p><strong>Risk Level:</strong> {diagnostic_report.risk_level.value}</p>")
            html_lines.append(f"<p><strong>Status:</strong> {diagnostic_report.current_status}</p>")

            if diagnostic_report.possible_causes:
                html_lines.append("<h4>Possible Causes:</h4>")
                html_lines.append("<ul>")
                for cause in diagnostic_report.possible_causes[:3]:
                    html_lines.append(f"<li>{cause}</li>")
                html_lines.append("</ul>")

            if diagnostic_report.recommended_actions:
                html_lines.append("<h4>Recommended Actions:</h4>")
                html_lines.append("<ol>")
                for action in diagnostic_report.recommended_actions[:5]:
                    html_lines.append(f"<li>{action}</li>")
                html_lines.append("</ol>")

        html_lines.append("</body></html>")
        html_content = "\n".join(html_lines)

        # Generate text version
        text_lines = [
            "BESS Alarm Notification",
            "=" * 40,
            f"Alarm ID: {alarm.alarm_id}",
            f"Alarm Type: {alarm.alarm_type}",
            f"Severity: {alarm.severity.value}",
            f"Timestamp: {alarm.timestamp.isoformat()}",
            f"Source: {alarm.source}",
        ]

        if device_data:
            text_lines.append("\nDevice Information:")
            for key, value in list(device_data.items())[:10]:
                text_lines.append(f"  {key}: {value}")

        if diagnostic_report:
            text_lines.append("\nDiagnostic Report:")
            text_lines.append(f"  Risk Level: {diagnostic_report.risk_level.value}")
            text_lines.append(f"  Status: {diagnostic_report.current_status}")

            if diagnostic_report.possible_causes:
                text_lines.append("\n  Possible Causes:")
                for i, cause in enumerate(diagnostic_report.possible_causes[:3], 1):
                    text_lines.append(f"    {i}. {cause}")

            if diagnostic_report.recommended_actions:
                text_lines.append("\n  Recommended Actions:")
                for i, action in enumerate(diagnostic_report.recommended_actions[:5], 1):
                    text_lines.append(f"    {i}. {action}")

        text_content = "\n".join(text_lines)

        return html_content, text_content

    @classmethod
    def from_config(cls, email_config: Dict[str, Any]) -> "EmailService":
        """
        Create email service from configuration

        Args:
            email_config: Email configuration from app.yaml

        Returns:
            EmailService instance
        """
        email_client = EmailClient.from_config(email_config)
        return cls(email_client=email_client, config=email_config)


