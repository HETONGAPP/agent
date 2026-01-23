"""
LLM Diagnostic Service
Flexible diagnostic report generation using LLM
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC

from ..models.alarm import Alarm
from ..models.diagnostic import DiagnosticReport, RiskLevel
from ..models.device_data import DeviceData
from .client import LLMClient
from .prompt_loader import PromptLoader
from .cache import DiagnosticCache

logger = logging.getLogger(__name__)


class LLMDiagnosticService:
    """
    Flexible LLM Diagnostic Service
    Generates diagnostic reports for alarms using LLM
    """

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_loader: Optional[PromptLoader] = None,
        cache: Optional[DiagnosticCache] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize diagnostic service

        Args:
            llm_client: LLM client instance
            prompt_loader: Prompt template loader (optional, will create default if not provided)
            cache: Diagnostic cache (optional)
            config: Service configuration
        """
        self.llm_client = llm_client
        self.config = config or {}
        self.cache_ttl = self.config.get("cache_ttl", 3600)

        # Initialize prompt loader
        if prompt_loader is None:
            template_dirs = self.config.get("prompt_templates_dir", ["prompts"])
            self.prompt_loader = PromptLoader(template_dirs=template_dirs)
        else:
            self.prompt_loader = prompt_loader

        # Initialize cache
        self.cache = cache
        self.enable_cache = self.config.get("enable_cache", True) if cache else False

        # System prompt for LLM
        self.system_prompt = self.config.get(
            "system_prompt",
            "You are a BESS (Battery Energy Storage System) operations expert. "
            "Provide concise, engineer-readable diagnostic reports.",
        )

    async def generate_diagnostic(
        self,
        alarm: Alarm,
        device_data: Optional[DeviceData] = None,
        rule: Optional[Dict[str, Any]] = None,
        history: Optional[List[Alarm]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticReport:
        """
        Generate diagnostic report for alarm

        Args:
            alarm: Alarm object
            device_data: Optional device data that triggered the alarm
            rule: Optional rule that matched
            history: Optional historical alarms for context
            additional_context: Optional additional context data

        Returns:
            DiagnosticReport object
        """
        # Check cache first
        if self.enable_cache and self.cache:
            context = self._build_cache_context(alarm, device_data, rule)
            cached = await self.cache.get(alarm.alarm_id, context)
            if cached:
                logger.info(f"Using cached diagnostic for alarm {alarm.alarm_id}")
                return DiagnosticReport.from_dict(cached)

        # Build prompt context
        prompt_context = self._build_prompt_context(alarm, device_data, rule, history, additional_context)

        # Get template name
        template_name = self.prompt_loader.get_template_name(
            alarm.alarm_type, device_data.device_type.value if device_data else None
        )

        # Render prompt
        try:
            prompt = self.prompt_loader.render(template_name, prompt_context)
        except Exception as e:
            logger.warning(f"Failed to load template {template_name}, using default: {e}")
            # Fallback to default template or simple prompt
            prompt = self._build_fallback_prompt(alarm, device_data, rule)

        # Generate diagnostic using LLM
        try:
            llm_response = await self.llm_client.generate(prompt, self.system_prompt)
            logger.info(f"Generated LLM response for alarm {alarm.alarm_id}")
        except Exception as e:
            logger.error(f"LLM generation failed for alarm {alarm.alarm_id}: {e}", exc_info=True)
            # Return fallback diagnostic
            return self._create_fallback_diagnostic(alarm, device_data, rule)

        # Parse LLM response
        diagnostic_report = self._parse_llm_response(llm_response, alarm)

        # Cache result
        if self.enable_cache and self.cache:
            context = self._build_cache_context(alarm, device_data, rule)
            await self.cache.set(
                alarm.alarm_id, context, diagnostic_report.to_dict(), ttl=self.cache_ttl
            )

        return diagnostic_report

    def _build_prompt_context(
        self,
        alarm: Alarm,
        device_data: Optional[DeviceData],
        rule: Optional[Dict[str, Any]],
        history: Optional[List[Alarm]],
        additional_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build context for prompt template"""
        context = {
            "alarm": alarm,
            "alarm_id": alarm.alarm_id,
            "alarm_type": alarm.alarm_type,
            "severity": alarm.severity.value,
            "timestamp": alarm.timestamp.isoformat(),
        }

        # Add device data
        if device_data:
            context["device_data"] = device_data
            context["device_id"] = device_data.device_id
            context["device_type"] = device_data.device_type.value
            # Add data fields for easy access in templates
            context.update(device_data.data)
            
            # Add device-type-specific data objects for template compatibility
            # Templates may expect bms_data, pcs_data, etc.
            if device_data.device_type.value == "BMS":
                # Create bms_data object for BMS templates
                bms_data = type('BMSData', (), {
                    'cell_voltages': device_data.data.get('cell_voltages', []),
                    'temperatures': device_data.data.get('temperatures', []),
                    'soc': device_data.data.get('soc', 0),
                    'soh': device_data.data.get('soh', 0),
                    'max_delta_v': device_data.data.get('max_delta_v', 0),
                    'max_voltage': device_data.data.get('max_voltage', 0),
                    'min_voltage': device_data.data.get('min_voltage', 0),
                    'max_temperature': device_data.data.get('max_temperature', 0),
                    'min_temperature': device_data.data.get('min_temperature', 0),
                })()
                context["bms_data"] = bms_data
            elif device_data.device_type.value == "PCS":
                # Create pcs_data object for PCS templates
                pcs_data = type('PCSData', (), {
                    'active_power': device_data.data.get('active_power', 0),
                    'reactive_power': device_data.data.get('reactive_power', 0),
                    'voltage': device_data.data.get('voltage', 0),
                    'current': device_data.data.get('current', 0),
                    'frequency': device_data.data.get('frequency', 0),
                    'efficiency': device_data.data.get('efficiency', 0),
                    'temperature': device_data.data.get('temperature', 0),
                })()
                context["pcs_data"] = pcs_data
        else:
            # Provide default empty objects for templates that expect them
            # This prevents "bms_data is undefined" errors in templates
            context["bms_data"] = type('BMSData', (), {
                'cell_voltages': [],
                'temperatures': [],
                'soc': 0,
                'soh': 0,
                'max_delta_v': 0,
                'max_voltage': 0,
                'min_voltage': 0,
                'max_temperature': 0,
                'min_temperature': 0,
            })()
            context["pcs_data"] = type('PCSData', (), {
                'active_power': 0,
                'reactive_power': 0,
                'voltage': 0,
                'current': 0,
                'frequency': 0,
                'efficiency': 0,
                'temperature': 0,
            })()

        # Add rule information
        if rule:
            context["rule"] = rule
            context["rule_id"] = rule.get("id")
            context["rule_name"] = rule.get("name")
            context["sop_reference"] = rule.get("metadata", {}).get("sop_reference", "")

        # Add history
        if history:
            context["history"] = history
            context["history_count"] = len([a for a in history if a.alarm_type == alarm.alarm_type])

        # Add additional context
        if additional_context:
            context.update(additional_context)

        return context

    async def generate_site_diagnostic(
        self,
        site_id: str,
        alarms: List[Alarm],
        devices: List[Dict[str, Any]],
        historical_data: Optional[List[Dict[str, Any]]] = None,
        time_range: str = "-24h",
    ) -> DiagnosticReport:
        """
        Generate comprehensive diagnostic report for a site
        
        This method analyzes all devices, alarms, and historical data for a site
        to provide a comprehensive diagnostic report.
        
        Args:
            site_id: Site ID
            alarms: List of alarms for this site
            devices: List of device information dictionaries
            historical_data: Optional historical device data (time series)
            time_range: Time range for historical data (e.g., "-24h", "-7d")
            
        Returns:
            DiagnosticReport object
        """
        # Build comprehensive context for site-level diagnosis
        context = {
            "site_id": site_id,
            "alarms": alarms,
            "alarm_count": len(alarms),
            "devices": devices,
            "device_count": len(devices),
            "historical_data": historical_data or [],
            "time_range": time_range,
        }
        
        # Group alarms by type and severity
        alarm_summary = {}
        for alarm in alarms:
            alarm_type = alarm.alarm_type
            severity = alarm.severity.value
            key = f"{alarm_type}:{severity}"
            if key not in alarm_summary:
                alarm_summary[key] = {
                    "alarm_type": alarm_type,
                    "severity": severity,
                    "count": 0,
                    "alarms": [],
                }
            alarm_summary[key]["count"] += 1
            alarm_summary[key]["alarms"].append(alarm)
        
        context["alarm_summary"] = list(alarm_summary.values())
        
        # Group devices by type
        devices_by_type = {}
        for device in devices:
            device_type = device.get("device_type", "UNKNOWN")
            if device_type not in devices_by_type:
                devices_by_type[device_type] = []
            devices_by_type[device_type].append(device)
        
        context["devices_by_type"] = devices_by_type
        
        # Analyze historical trends if available
        if historical_data:
            context["historical_analysis"] = self._analyze_historical_trends(historical_data)
        
        # Build prompt for site-level diagnosis
        prompt = self._build_site_diagnostic_prompt(context)
        
        # Generate diagnostic using LLM
        try:
            system_prompt = (
                "You are a BESS (Battery Energy Storage System) operations expert. "
                "Analyze the entire site's status, including all devices, alarms, and historical data. "
                "Provide a comprehensive diagnostic report that considers system-wide patterns and correlations. "
                "Identify root causes that may affect multiple devices and provide actionable recommendations."
            )
            
            llm_response = await self.llm_client.generate(prompt, system_prompt)
            logger.info(f"Generated LLM response for site {site_id} diagnostic")
        except Exception as e:
            logger.error(f"LLM generation failed for site {site_id}: {e}", exc_info=True)
            # Return fallback diagnostic
            return self._create_site_fallback_diagnostic(site_id, alarms, devices)
        
        # Parse LLM response
        # Use the first alarm ID as the primary alarm_id, or generate a composite one
        primary_alarm_id = alarms[0].alarm_id if alarms else f"site_{site_id}_diagnostic"
        diagnostic_report = self._parse_llm_response(llm_response, alarms[0] if alarms else None)
        diagnostic_report.alarm_id = primary_alarm_id
        
        # Clean the report using FormatterAgent
        try:
            from ..diagnostic_agent.agents.formatter import FormatterAgent
            formatter = FormatterAgent(self.llm_client)
            
            # Clean markdown field first
            if diagnostic_report.markdown:
                diagnostic_report.markdown = await formatter.format_text(diagnostic_report.markdown)
            
            # Clean current_status field
            if diagnostic_report.current_status:
                cleaned_status = await formatter.format_text(diagnostic_report.current_status)
                if cleaned_status:
                    cleaned_status = cleaned_status.strip()
                    # Remove any remaining ** or * symbols (extra safety)
                    for _ in range(20):
                        cleaned_status = cleaned_status.replace('**', '')
                        cleaned_status = cleaned_status.replace('*', '')
                    cleaned_status = cleaned_status.replace('`', '')
                    diagnostic_report.current_status = cleaned_status
            
            # Clean list fields - each item individually
            if diagnostic_report.recommended_actions:
                cleaned_actions = []
                for action in diagnostic_report.recommended_actions:
                    # Clean each action item
                    cleaned = await formatter.format_text(action)
                    if cleaned:
                        cleaned = cleaned.strip()
                        # Remove any remaining ** or * symbols (extra safety)
                        for _ in range(20):
                            cleaned = cleaned.replace('**', '')
                            cleaned = cleaned.replace('*', '')
                        cleaned = cleaned.replace('`', '')
                        if len(cleaned) > 3:
                            cleaned_actions.append(cleaned)
                diagnostic_report.recommended_actions = cleaned_actions
            
            if diagnostic_report.possible_causes:
                cleaned_causes = []
                for cause in diagnostic_report.possible_causes:
                    # Clean each cause item
                    cleaned = await formatter.format_text(cause)
                    if cleaned:
                        cleaned = cleaned.strip()
                        # Remove any remaining ** or * symbols (extra safety)
                        for _ in range(20):
                            cleaned = cleaned.replace('**', '')
                            cleaned = cleaned.replace('*', '')
                        cleaned = cleaned.replace('`', '')
                        if len(cleaned) > 3:
                            cleaned_causes.append(cleaned)
                diagnostic_report.possible_causes = cleaned_causes
            
            if diagnostic_report.references:
                cleaned_refs = []
                for ref in diagnostic_report.references:
                    # Clean each reference item
                    cleaned = await formatter.format_text(ref)
                    if cleaned:
                        cleaned = cleaned.strip()
                        # Remove any remaining ** or * symbols (extra safety)
                        for _ in range(20):
                            cleaned = cleaned.replace('**', '')
                            cleaned = cleaned.replace('*', '')
                        cleaned = cleaned.replace('`', '')
                        if len(cleaned) > 3:
                            cleaned_refs.append(cleaned)
                diagnostic_report.references = cleaned_refs
        except Exception as e:
            logger.warning(f"Failed to format diagnostic report using FormatterAgent: {e}")
        
        return diagnostic_report

    def _analyze_historical_trends(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze historical data trends"""
        if not historical_data:
            return {}
        
        # Group by metric and device
        metrics = {}
        for point in historical_data:
            metric = point.get("metric", "unknown")
            device_id = point.get("device_id", "unknown")
            value = point.get("value")
            timestamp = point.get("timestamp")
            
            if metric not in metrics:
                metrics[metric] = {}
            if device_id not in metrics[metric]:
                metrics[metric][device_id] = []
            
            if value is not None and timestamp:
                metrics[metric][device_id].append({"value": value, "timestamp": timestamp})
        
        # Calculate trends (simple: compare first and last values)
        trends = {}
        for metric, devices in metrics.items():
            trends[metric] = {}
            for device_id, values in devices.items():
                if len(values) >= 2:
                    sorted_values = sorted(values, key=lambda x: x["timestamp"])
                    first_value = sorted_values[0]["value"]
                    last_value = sorted_values[-1]["value"]
                    trend = "increasing" if last_value > first_value else "decreasing" if last_value < first_value else "stable"
                    change = abs(last_value - first_value)
                    trends[metric][device_id] = {
                        "trend": trend,
                        "change": change,
                        "first_value": first_value,
                        "last_value": last_value,
                    }
        
        return trends

    def _build_site_diagnostic_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for site-level diagnosis"""
        prompt = f"""Generate a comprehensive diagnostic report for BESS Site {context['site_id']}.

## Site Overview
- Site ID: {context['site_id']}
- Total Devices: {context['device_count']}
- Total Alarms: {context['alarm_count']}
- Analysis Time Range: {context['time_range']}

## Devices Status
"""
        for device_type, devices in context.get("devices_by_type", {}).items():
            prompt += f"\n### {device_type} Devices ({len(devices)}):\n"
            for device in devices[:5]:  # Limit to first 5 devices per type
                device_id = device.get("device_id", "unknown")
                status = device.get("status", "unknown")
                prompt += f"- Device {device_id}: Status = {status}\n"
        
        prompt += "\n## Alarm Summary\n"
        for summary in context.get("alarm_summary", [])[:10]:  # Limit to top 10 alarm types
            prompt += f"- {summary['alarm_type']} ({summary['severity']}): {summary['count']} occurrence(s)\n"
        
        if context.get("historical_analysis"):
            prompt += "\n## Historical Trends\n"
            for metric, devices in list(context["historical_analysis"].items())[:5]:
                prompt += f"\n### {metric}:\n"
                for device_id, trend_info in list(devices.items())[:3]:
                    prompt += f"- Device {device_id}: {trend_info['trend']} (change: {trend_info['change']:.2f})\n"
        
        prompt += """
## Analysis Request
Please provide:
1. **Current Status**: Overall site health assessment
2. **Risk Level**: Low/Medium/High based on alarm patterns and device status
3. **Root Causes**: Identify potential root causes considering all devices and alarms
4. **Correlations**: Note any patterns or correlations between different devices/alarms
5. **Recommended Actions**: Prioritized action items for the site
6. **References**: Relevant SOP references if applicable

Focus on system-wide analysis rather than individual device issues.
"""
        
        return prompt

    def _create_site_fallback_diagnostic(
        self, site_id: str, alarms: List[Alarm], devices: List[Dict[str, Any]]
    ) -> DiagnosticReport:
        """Create fallback diagnostic when LLM fails for site"""
        # Determine risk level based on alarm severities
        has_critical = any(a.severity.value == "Critical" for a in alarms)
        has_warning = any(a.severity.value == "Warning" for a in alarms)
        
        if has_critical:
            risk_level = RiskLevel.HIGH
        elif has_warning:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        current_status = (
            f"Site {site_id} has {len(alarms)} active alarm(s) across {len(devices)} device(s). "
            f"LLM diagnostic generation failed."
        )
        
        possible_causes = [
            "Multiple devices showing anomalies",
            "System-wide pattern detected",
            "Potential cascading failure",
        ]
        
        recommended_actions = [
            "Review all device statuses",
            "Check system logs",
            "Verify site configuration",
            "Consult SOP documentation",
        ]
        
        primary_alarm_id = alarms[0].alarm_id if alarms else f"site_{site_id}_diagnostic"
        
        return DiagnosticReport(
            alarm_id=primary_alarm_id,
            current_status=current_status,
            risk_level=risk_level,
            possible_causes=possible_causes,
            recommended_actions=recommended_actions,
            references=[],
            generated_at=datetime.now(UTC),
            markdown=f"# Site Diagnostic Report\n\n{current_status}",
        )

    def _parse_llm_response(self, response: str, alarm: Optional[Alarm] = None) -> DiagnosticReport:
        """
        Parse LLM response into DiagnosticReport
        Flexible parsing that handles various response formats
        """
        # Extract risk level
        risk_level = self._extract_risk_level(response)

        # Extract current status
        current_status = self._extract_section(response, ["Current Status", "Status Description", "What happened"])

        # Extract possible causes
        possible_causes = self._extract_list_section(
            response, ["Possible Causes", "Possible Reasons", "Root Causes"]
        )

        # Extract recommended actions
        recommended_actions = self._extract_list_section(
            response, ["Recommended Actions", "Actions", "Recommended Steps"]
        )

        # Extract references
        references = self._extract_list_section(response, ["References", "Reference", "SOP Reference"])

        # If parsing failed, use full response as current status
        if not current_status:
            current_status = response[:500]  # Limit length

        alarm_id = alarm.alarm_id if alarm else "unknown"
        
        return DiagnosticReport(
            alarm_id=alarm_id,
            current_status=current_status or "Diagnostic generated",
            risk_level=risk_level,
            possible_causes=possible_causes[:3],  # Limit to top 3
            recommended_actions=recommended_actions[:5],  # Limit to top 5
            references=references,
            generated_at=datetime.now(UTC),
            markdown=response,
        )

    def _build_cache_context(
        self, alarm: Alarm, device_data: Optional[DeviceData], rule: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build context for cache key generation"""
        context = {
            "alarm_type": alarm.alarm_type,
            "severity": alarm.severity.value,
        }

        if device_data:
            context["device_type"] = device_data.device_type.value
            context["device_id"] = device_data.device_id

        if rule:
            context["rule_id"] = rule.get("id")

        return context

    def _build_fallback_prompt(
        self, alarm: Alarm, device_data: Optional[DeviceData], rule: Optional[Dict[str, Any]]
    ) -> str:
        """Build fallback prompt if template not found"""
        prompt = f"""Generate a diagnostic report for the following BESS alarm:

Alarm ID: {alarm.alarm_id}
Alarm Type: {alarm.alarm_type}
Severity: {alarm.severity.value}
Timestamp: {alarm.timestamp.isoformat()}
"""

        if device_data:
            prompt += f"\nDevice Information:\n"
            prompt += f"- Device ID: {device_data.device_id}\n"
            prompt += f"- Device Type: {device_data.device_type.value}\n"
            for key, value in list(device_data.data.items())[:10]:  # Limit to first 10 fields
                prompt += f"- {key}: {value}\n"

        if rule:
            prompt += f"\nRule Information:\n"
            prompt += f"- Rule ID: {rule.get('id')}\n"
            prompt += f"- Rule Name: {rule.get('name')}\n"

        prompt += """
Please provide:
1. Current status description
2. Risk level (Low/Medium/High)
3. Top 3 possible causes
4. Recommended actions
5. References
"""

        return prompt

    def _parse_llm_response(self, response: str, alarm: Optional[Alarm] = None) -> DiagnosticReport:
        """
        Parse LLM response into DiagnosticReport
        Flexible parsing that handles various response formats
        """
        # Extract risk level
        risk_level = self._extract_risk_level(response)

        # Extract current status
        current_status = self._extract_section(response, ["Current Status", "Status Description", "What happened"])

        # Extract possible causes
        possible_causes = self._extract_list_section(
            response, ["Possible Causes", "Possible Reasons", "Root Causes"]
        )

        # Extract recommended actions
        recommended_actions = self._extract_list_section(
            response, ["Recommended Actions", "Actions", "Recommended Steps"]
        )

        # Extract references
        references = self._extract_list_section(response, ["References", "Reference", "SOP Reference"])

        # If parsing failed, use full response as current status
        if not current_status:
            current_status = response[:500]  # Limit length

        alarm_id = alarm.alarm_id if alarm else "unknown"
        
        return DiagnosticReport(
            alarm_id=alarm_id,
            current_status=current_status or "Diagnostic generated",
            risk_level=risk_level,
            possible_causes=possible_causes[:3],  # Limit to top 3
            recommended_actions=recommended_actions[:5],  # Limit to top 5
            references=references,
            generated_at=datetime.now(UTC),
            markdown=response,
        )

    def _extract_risk_level(self, text: str) -> RiskLevel:
        """Extract risk level from text"""
        text_lower = text.lower()
        if "high" in text_lower and "risk" in text_lower:
            return RiskLevel.HIGH
        elif "medium" in text_lower and "risk" in text_lower:
            return RiskLevel.MEDIUM
        elif "low" in text_lower and "risk" in text_lower:
            return RiskLevel.LOW
        # Default based on severity keywords
        if any(word in text_lower for word in ["critical", "urgent", "severe", "danger"]):
            return RiskLevel.HIGH
        elif any(word in text_lower for word in ["warning", "caution", "moderate"]):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _extract_section(self, text: str, section_names: List[str]) -> Optional[str]:
        """Extract section content from text"""
        for section_name in section_names:
            # Try various patterns
            patterns = [
                rf"(?i){re.escape(section_name)}[:\-]?\s*\n(.*?)(?=\n\*\*|\n##|\n-|\Z)",
                rf"(?i){re.escape(section_name)}[:\-]?\s*(.*?)(?=\n\*\*|\n##|\n-|\Z)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
                if match:
                    content = match.group(1).strip()
                    if content:
                        return content
        return None

    def _extract_list_section(self, text: str, section_names: List[str]) -> List[str]:
        """Extract list items from section"""
        section_text = self._extract_section(text, section_names)
        if not section_text:
            return []

        items = []
        # Try to extract numbered or bulleted items
        patterns = [
            r"(?i)^\s*[0-9]+[\.\)]\s*(.+)$",  # Numbered: 1. item
            r"(?i)^\s*[-*•]\s*(.+)$",  # Bulleted: - item
            r"(?i)^\s*[0-9]+\.\s*(.+)$",  # Numbered: 1. item (alternative)
        ]

        for line in section_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Remove markdown symbols aggressively before matching
            for _ in range(50):
                line = line.replace('**', '')
                line = line.replace('*', '')
            for _ in range(20):
                line = line.replace('`', '')
            
            # Skip section labels
            line_lower = line.lower()
            if (line_lower.startswith('immediate action') or
                line_lower.startswith('short-term action') or
                line_lower.startswith('long-term action') or
                'immediate actions' in line_lower or
                'short-term actions' in line_lower or
                'long-term actions' in line_lower):
                continue
            
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    item = match.group(1).strip()
                    
                    # Clean up the item (aggressive cleanup)
                    for _ in range(50):
                        item = item.replace('**', '')
                        item = item.replace('*', '')
                    for _ in range(20):
                        item = item.replace('`', '')
                    
                    # Remove patterns like "(Highest Priority):" or "(Priority):"
                    item = re.sub(r'\s*\([^\)]*priority[^\)]*\):\s*', ': ', item, flags=re.IGNORECASE)
                    
                    # Remove common prefixes
                    item = re.sub(r'^(Action Item\s*\d*[:\-]?\s*)', '', item, flags=re.IGNORECASE)
                    item = re.sub(r'^(Action[:\-]?\s*)', '', item, flags=re.IGNORECASE)
                    item = re.sub(r'^(Immediate\s+Actions?|Short-Term\s+Actions?|Long-Term\s+Actions?):\s*', '', item, flags=re.IGNORECASE)
                    
                    # Remove colons at the end
                    if item.endswith(':'):
                        item = item.rstrip(':')
                    
                    # Clean up spaces
                    item = re.sub(r'\s+', ' ', item).strip()
                    
                    if item and len(item) > 3:
                        items.append(item)
                    break

        return items

    def _create_fallback_diagnostic(
        self, alarm: Alarm, device_data: Optional[DeviceData], rule: Optional[Dict[str, Any]]
    ) -> DiagnosticReport:
        """Create fallback diagnostic when LLM fails"""
        # Determine risk level from severity
        if alarm.severity.value == "Critical":
            risk_level = RiskLevel.HIGH
        elif alarm.severity.value == "Warning":
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        current_status = f"Alarm {alarm.alarm_type} detected. LLM diagnostic generation failed."

        possible_causes = [
            "System monitoring detected anomaly",
            "Device data indicates potential issue",
            "Rule-based detection triggered",
        ]

        recommended_actions = [
            "Review device data and logs",
            "Check system status",
            "Consult SOP documentation",
        ]

        references = []
        if rule:
            sop_ref = rule.get("metadata", {}).get("sop_reference")
            if sop_ref:
                references.append(sop_ref)

        return DiagnosticReport(
            alarm_id=alarm.alarm_id,
            current_status=current_status,
            risk_level=risk_level,
            possible_causes=possible_causes,
            recommended_actions=recommended_actions,
            references=references,
            generated_at=datetime.now(UTC),
            markdown=f"# Diagnostic Report\n\n{current_status}",
        )

    @classmethod
    def from_config(
        cls, llm_config: Dict[str, Any], cache_config: Optional[Dict[str, Any]] = None
    ) -> "LLMDiagnosticService":
        """
        Create diagnostic service from configuration

        Args:
            llm_config: LLM configuration from app.yaml
            cache_config: Optional cache configuration

        Returns:
            LLMDiagnosticService instance
        """
        # Create LLM client
        llm_client = LLMClient.from_config(llm_config)

        # Create cache if configured
        cache = None
        if cache_config:
            cache_type = cache_config.get("type", "redis")
            cache = DiagnosticCache(cache_type=cache_type, config=cache_config)

        # Create service
        return cls(llm_client=llm_client, cache=cache, config=llm_config)



