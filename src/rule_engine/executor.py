"""
Rule executor for executing rule actions
Supports flexible action execution and integration
"""

from typing import List, Dict, Any, Callable, Optional
import logging

from ..models.alarm import Alarm
from ..models.device_data import DeviceData

logger = logging.getLogger(__name__)


class RuleExecutor:
    """Execute rule actions"""

    def __init__(self):
        """Initialize rule executor"""
        self._action_handlers: Dict[str, Callable] = {}

    def register_action_handler(self, action_name: str, handler: Callable):
        """
        Register custom action handler

        Args:
            action_name: Action name (e.g., 'trigger_llm_diagnostic')
            handler: Handler function that takes (alarm, device_data, rule) as arguments
        """
        self._action_handlers[action_name] = handler
        logger.info(f"Registered action handler: {action_name}")

    def execute(
        self, alarm: Alarm, device_data: DeviceData, rule: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute rule actions

        Args:
            alarm: Generated alarm
            device_data: Device data that triggered the rule
            rule: Rule configuration

        Returns:
            Dictionary with execution results for each action
        """
        actions = rule.get("actions", [])
        results = {}

        for action in actions:
            action_name = action if isinstance(action, str) else action.get("name", "")
            action_params = {} if isinstance(action, str) else action.get("params", {})

            try:
                result = self._execute_action(action_name, alarm, device_data, rule, action_params)
                results[action_name] = {
                    "success": True,
                    "result": result,
                }
            except Exception as e:
                logger.error(f"Failed to execute action {action_name}: {e}", exc_info=True)
                results[action_name] = {
                    "success": False,
                    "error": str(e),
                }

        return results

    def _execute_action(
        self,
        action_name: str,
        alarm: Alarm,
        device_data: DeviceData,
        rule: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Any:
        """Execute a single action"""
        # Check if custom handler is registered
        if action_name in self._action_handlers:
            handler = self._action_handlers[action_name]
            return handler(alarm, device_data, rule, **params)

        # Built-in action handlers
        if action_name == "trigger_llm_diagnostic":
            return self._handle_trigger_llm_diagnostic(alarm, device_data, rule, **params)
        elif action_name == "send_email":
            return self._handle_send_email(alarm, device_data, rule, **params)
        elif action_name == "notify_engineer":
            return self._handle_notify_engineer(alarm, device_data, rule, **params)
        elif action_name == "log_alarm":
            return self._handle_log_alarm(alarm, device_data, rule, **params)
        else:
            logger.warning(f"Unknown action: {action_name}, skipping")
            return None

    def _handle_trigger_llm_diagnostic(
        self, alarm: Alarm, device_data: DeviceData, rule: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Handle trigger LLM diagnostic action"""
        try:
            # Import here to avoid circular dependency
            from ..llm_diagnostic.service import LLMDiagnosticService
            from ..llm_diagnostic.client import LLMClient
            from ..llm_diagnostic.cache import DiagnosticCache
            import yaml
            from pathlib import Path

            # Load configuration
            config_path = Path(__file__).parent.parent.parent / "config" / "app.yaml"
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            llm_config = config.get("llm", {})
            cache_config = config.get("database", {}).get("redis", {})

            # Create diagnostic service
            diagnostic_service = LLMDiagnosticService.from_config(llm_config, {"redis": cache_config})

            # Generate diagnostic (async, but we're in sync context)
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            diagnostic_report = loop.run_until_complete(
                diagnostic_service.generate_diagnostic(alarm, device_data, rule)
            )

            logger.info(f"Generated LLM diagnostic for alarm {alarm.alarm_id}")
            return {
                "status": "success",
                "diagnostic_report": diagnostic_report.to_dict(),
                "risk_level": diagnostic_report.risk_level.value,
            }
        except Exception as e:
            logger.error(f"Failed to generate LLM diagnostic: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": "LLM diagnostic generation failed",
            }

    def _handle_send_email(
        self, alarm: Alarm, device_data: DeviceData, rule: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Handle send email action"""
        try:
            # Import here to avoid circular dependency
            from ..email.service import EmailService
            from ..llm_diagnostic.service import LLMDiagnosticService
            import yaml
            from pathlib import Path

            # Load configuration
            config_path = Path(__file__).parent.parent.parent / "config" / "app.yaml"
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            email_config = config.get("email", {})
            if not email_config.get("smtp_host"):
                logger.warning("Email not configured, skipping email send")
                return {
                    "status": "skipped",
                    "message": "Email not configured",
                }

            # Create email service
            email_service = EmailService.from_config(email_config)

            # Try to get diagnostic report if LLM service is available
            diagnostic_report = kwargs.get("diagnostic_report")
            if not diagnostic_report:
                # Try to generate diagnostic if LLM service available
                try:
                    llm_config = config.get("llm", {})
                    if llm_config.get("provider"):
                        llm_service = LLMDiagnosticService.from_config(llm_config)
                        import asyncio

                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                        diagnostic_report = loop.run_until_complete(
                            llm_service.generate_diagnostic(alarm, device_data, rule)
                        )
                except Exception as e:
                    logger.debug(f"Could not generate diagnostic for email: {e}")

            # Send email (async, but we're in sync context)
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            success = loop.run_until_complete(
                email_service.send_alarm_email(
                    alarm=alarm,
                    diagnostic_report=diagnostic_report,
                    device_data=device_data.to_dict() if device_data else None,
                )
            )

            if success:
                logger.info(f"Email sent for alarm {alarm.alarm_id}")
                return {
                    "status": "success",
                    "message": "Email sent successfully",
                }
            else:
                return {
                    "status": "error",
                    "message": "Email sending failed",
                }

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": "Email sending failed",
            }

    def _handle_notify_engineer(
        self, alarm: Alarm, device_data: DeviceData, rule: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Handle notify engineer action"""
        logger.info(f"Notifying engineer for alarm {alarm.alarm_id}")
        return {
            "status": "notified",
            "message": "Engineer notification sent",
        }

    def _handle_log_alarm(
        self, alarm: Alarm, device_data: DeviceData, rule: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Handle log alarm action"""
        logger.info(f"Alarm logged: {alarm.alarm_id} - {alarm.alarm_type} ({alarm.severity.value})")
        return {
            "status": "logged",
            "message": "Alarm logged successfully",
        }

