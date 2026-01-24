"""
Report Generator Agent
Generates comprehensive diagnostic reports
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient
from ...models.diagnostic import DiagnosticReport, RiskLevel
from .formatter import FormatterAgent
from ..variable_knowledge import (
    get_variable_info,
    get_related_variables,
    validate_variable_exists,
)
from ...utils.debug import debug_print, is_debug_mode

logger = logging.getLogger(__name__)


class ReportGeneratorAgent(BaseDiagnosticAgent):
    """Agent for generating comprehensive diagnostic reports"""

    SYSTEM_PROMPT = """You are an EMS (Energy Management System) expert and diagnostic report generation specialist for BESS (Battery Energy Storage System) operations.

Your role is to synthesize all analysis results into a comprehensive, accurate, and actionable diagnostic report.

## Your Expertise
- You have deep knowledge of BESS operations, energy management, device interactions, and system health monitoring
- You think like an experienced field engineer who has seen many real-world scenarios
- You apply rigorous analysis: ask "why" multiple times (5 Why method) to get to root causes
- You validate your conclusions: Is this correct? Can I understand it? Is this a real problem? Is this actionable or just vague?

## Report Structure
Generate a professional, structured diagnostic report with these exact sections:
1. Current Status: Overall site health assessment (2-3 sentences)
2. Risk Level: Low/Medium/High with brief justification
3. Root Causes: Bullet list of identified root causes (3-5 items)
4. Recommended Actions: Bullet list of prioritized actions (3-5 items)
5. References: Bullet list of SOP references if applicable

## Critical Analysis Principles
1. **Data Validation**: Before making any conclusions, verify:
   - Are there actual alarms? (not just "no alarms" message)
   - Are there registered devices? (not just empty device list)
   - Is there real-time data? (not just device registration)
   - Is there historical data? (not just empty time series)
   - What device types are present? (single device type vs. mixed types)

2. **EMS Expert Perspective**: 
   - Consider system-level interactions, not just individual components
   - Understand that a single device type site has different characteristics than multi-device sites
   - Recognize that device registration alone does not indicate operational issues
   - Distinguish between "no data" and "normal operation"

3. **5 Why Analysis**: For each identified issue, ask:
   - Why did this happen? (First why)
   - Why did that occur? (Second why)
   - Why did that happen? (Third why)
   - Continue until reaching the true root cause

4. **Self-Validation**: Before finalizing each section, ask:
   - Is this statement correct based on the data?
   - Can a field engineer understand and act on this?
   - Is this a real, specific problem or just generic/vague?
   - Is this actionable or just "monitor more"?

5. **Honesty About Limitations**:
   - If there are no alarms, state clearly: "No alarms detected"
   - If there's only device registration but no operational data, state: "Insufficient operational data"
   - If there's only one device type, acknowledge this in your analysis
   - Never fabricate problems that aren't supported by the data

Use clear, professional language. Focus on accuracy, specificity, and actionable insights. Avoid generic statements.
"""

    def __init__(self, llm_client: LLMClient):
        """Initialize report generator agent"""
        super().__init__(self.SYSTEM_PROMPT, llm_client, "ReportGeneratorAgent")
        # Initialize formatter agent for cleaning reports
        self.formatter = FormatterAgent(llm_client)

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report"""
        site_id = context.get("site_id")

        # Collect all analysis results from dependencies and context
        all_results = {}
        
        # First, try to get all completed results from context (for ReportGeneratorAgent)
        all_completed_results = context.get("all_completed_results", [])
        if all_completed_results:
            if is_debug_mode():
                logger.warning(f"[ReportGenerator] ⚠️ Found {len(all_completed_results)} completed task results in context")
                debug_print(f"[ReportGenerator] ⚠️ Found {len(all_completed_results)} completed task results in context")
            for completed_task in all_completed_results:
                dep_result = completed_task.get("result", {})
                agent = dep_result.get("agent", "") or completed_task.get("agent", "")
                if is_debug_mode():
                    logger.warning(f"[ReportGenerator] ⚠️ Completed task agent: {agent}, status: {dep_result.get('status')}")
                    debug_print(f"[ReportGenerator] ⚠️ Completed task agent: {agent}, status: {dep_result.get('status')}")
                if agent:
                    all_results[agent] = dep_result
        
        # Also collect from direct dependencies (fallback)
        if dependencies:
            if is_debug_mode():
                logger.warning(f"[ReportGenerator] ⚠️ Also collecting from {len(dependencies)} direct dependencies")
                debug_print(f"[ReportGenerator] ⚠️ Also collecting from {len(dependencies)} direct dependencies")
            for dep in dependencies:
                dep_result = dep.get("result", {})
                agent = dep_result.get("agent", "")
                if agent and agent not in all_results:  # Don't overwrite if already in all_results
                    if is_debug_mode():
                        logger.warning(f"[ReportGenerator] ⚠️ Dependency agent: {agent}, status: {dep_result.get('status')}")
                        debug_print(f"[ReportGenerator] ⚠️ Dependency agent: {agent}, status: {dep_result.get('status')}")
                    all_results[agent] = dep_result
        
        if is_debug_mode():
            logger.warning(f"[ReportGenerator] ⚠️ Final collected results from agents: {list(all_results.keys())}")
            debug_print(f"[ReportGenerator] ⚠️ Final collected results from agents: {list(all_results.keys())}")

        if not all_results:
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": "No analysis results available from dependencies",
                "site_id": site_id,
            }

        try:
            # Build report generation prompt
            prompt = self._build_report_prompt(all_results, site_id)

            # Call LLM to generate report
            report_text = await self.llm_client.generate(prompt, self.system_prompt)

            # Use FormatterAgent to clean the report text (specialized agent for formatting)
            logger.info("[ReportGeneratorAgent] Using FormatterAgent to clean report text")
            formatted_result = await self.formatter.format_text(report_text)
            report_text = formatted_result

            # Parse report into structured format
            diagnostic_report = await self._parse_report(report_text, site_id, all_results)
            
            # Clean the markdown field using FormatterAgent
            if diagnostic_report.markdown:
                diagnostic_report.markdown = await self.formatter.format_text(diagnostic_report.markdown)

            return {
                "status": "success",
                "agent": self.agent_name,
                "report": diagnostic_report.to_dict(),
                "markdown": report_text,
                "site_id": site_id,
            }

        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            # Return fallback report
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": str(e),
                "fallback_report": self._create_fallback_report(site_id, all_results),
                "site_id": site_id,
            }

    def _build_report_prompt(
        self, all_results: Dict[str, Dict[str, Any]], site_id: str
    ) -> str:
        """Build report generation prompt"""
        prompt = f"""Generate a comprehensive diagnostic report for BESS Site {site_id}.

**⚠️ CRITICAL INSTRUCTION BEFORE YOU START:**
- You will see a "Data Availability Summary" section below that shows the EXACT number of alarms
- If that number is > 0, you MUST mention alarms in the "Current Status" section
- DO NOT say "No alarms detected" if the summary shows alarms exist - this is a contradiction
- The alarm count in the summary is ACCURATE and comes directly from the analysis

## Analysis Results Summary
"""

        # Include all analysis results
        if "AlarmAnalyzerAgent" in all_results:
            result = all_results["AlarmAnalyzerAgent"]
            if result.get("status") == "success":
                prompt += "\n### Alarm Analysis:\n"
                analysis = result.get("analysis", "")
                if analysis:
                    # Include full analysis, not just preview
                    prompt += f"{analysis}\n"
                insights = result.get("insights", {})
                alarm_count = insights.get("total_alarms", 0)
                critical_count = insights.get("critical_count", 0)
                warning_count = insights.get("warning_count", 0)
                info_count = insights.get("info_count", 0)
                by_type = insights.get("by_type", {})
                by_severity = insights.get("by_severity", {})
                
                prompt += f"\n**Alarm Statistics:**\n"
                prompt += f"- Total Alarms: {alarm_count}\n"
                prompt += f"- Critical Alarms: {critical_count}\n"
                prompt += f"- Warning Alarms: {warning_count}\n"
                prompt += f"- Info Alarms: {info_count}\n"
                
                if by_type:
                    prompt += f"\n**Alarms by Type:**\n"
                    for alarm_type, count in by_type.items():
                        prompt += f"- {alarm_type}: {count} alarm(s)\n"
                
                if by_severity:
                    prompt += f"\n**Alarms by Severity:**\n"
                    for severity, count in by_severity.items():
                        if count > 0:
                            prompt += f"- {severity}: {count} alarm(s)\n"
                
                # Add explicit note if alarms exist
                if alarm_count > 0:
                    prompt += f"\n**⚠️ IMPORTANT: {alarm_count} alarm(s) were detected. You MUST mention these alarms in the Current Status section of your report.**\n"

        if "DeviceAnalyzerAgent" in all_results:
            result = all_results["DeviceAnalyzerAgent"]
            if result.get("status") == "success":
                prompt += "\n### Device Analysis:\n"
                analysis = result.get("analysis", "")
                if analysis:
                    preview = analysis[:300] + "..." if len(analysis) > 300 else analysis
                    prompt += f"{preview}\n"
                insights = result.get("insights", {})
                prompt += f"- Total Devices: {insights.get('total_devices', 0)}\n"
                prompt += f"- Unhealthy Devices: {insights.get('unhealthy_count', 0)}\n"

        if "TrendAnalyzerAgent" in all_results:
            result = all_results["TrendAnalyzerAgent"]
            if result.get("status") == "success":
                prompt += "\n### Trend Analysis:\n"
                analysis = result.get("analysis", "")
                if analysis:
                    preview = analysis[:300] + "..." if len(analysis) > 300 else analysis
                    prompt += f"{preview}\n"
                # Add variable validation information
                insights = result.get("insights", {})
                variable_validations = insights.get("variable_validations", {})
                if variable_validations:
                    prompt += "\n**Variable Validation Summary:**\n"
                    for var_name, validation in list(variable_validations.items())[:5]:
                        var_info = validation.get("variable_info", {})
                        prompt += f"- {var_name}: {validation.get('valid_device_count', 0)}/{validation.get('total_device_count', 0)} devices valid"
                        prompt += f" (Role: {var_info.get('role', 'N/A')[:50]}...)\n"

        if "CorrelationAgent" in all_results:
            result = all_results["CorrelationAgent"]
            if result.get("status") == "success":
                prompt += "\n### Correlation Analysis:\n"
                analysis = result.get("analysis", "")
                if analysis:
                    preview = analysis[:300] + "..." if len(analysis) > 300 else analysis
                    prompt += f"{preview}\n"

        # Detailed data validation
        has_alarms = False
        alarm_count = 0
        critical_alarm_count = 0
        has_devices = False
        device_count = 0
        device_types = set()
        has_realtime_data = False
        has_historical_data = False
        historical_data_points = 0
        metrics_available = []
        
        if "AlarmAnalyzerAgent" in all_results:
            result = all_results["AlarmAnalyzerAgent"]
            if is_debug_mode():
                logger.warning(f"[ReportGenerator] ⚠️ AlarmAnalyzerAgent result status: {result.get('status')}")
                debug_print(f"[ReportGenerator] ⚠️ AlarmAnalyzerAgent result status: {result.get('status')}")
            if result.get("status") == "success":
                insights = result.get("insights", {})
                alarm_count = insights.get("total_alarms", 0)
                critical_alarm_count = insights.get("critical_count", 0)
                if is_debug_mode():
                    logger.warning(f"[ReportGenerator] ⚠️ Alarm count from insights: {alarm_count}, critical: {critical_alarm_count}")
                    debug_print(f"[ReportGenerator] ⚠️ Alarm count: {alarm_count}, critical: {critical_alarm_count}")
                    debug_print(f"[ReportGenerator] ⚠️ Full insights: {insights}")
                if alarm_count > 0:
                    has_alarms = True
                    if is_debug_mode():
                        logger.warning(f"[ReportGenerator] ⚠️ ✓ Alarms detected: {alarm_count} total, {critical_alarm_count} critical")
                        debug_print(f"[ReportGenerator] ⚠️ ✓ Alarms detected: {alarm_count} total, {critical_alarm_count} critical")
                else:
                    if is_debug_mode():
                        logger.warning(f"[ReportGenerator] ⚠️ ✗ No alarms detected (alarm_count={alarm_count})")
                        debug_print(f"[ReportGenerator] ⚠️ ✗ No alarms detected (alarm_count={alarm_count})")
            else:
                if is_debug_mode():
                    logger.warning(f"[ReportGenerator] ⚠️ AlarmAnalyzerAgent failed: {result.get('error', 'Unknown error')}")
                    debug_print(f"[ReportGenerator] ⚠️ AlarmAnalyzerAgent failed: {result.get('error', 'Unknown error')}")
        else:
            if is_debug_mode():
                logger.warning(f"[ReportGenerator] ⚠️ AlarmAnalyzerAgent not found in all_results. Available agents: {list(all_results.keys())}")
                debug_print(f"[ReportGenerator] ⚠️ AlarmAnalyzerAgent not found in all_results. Available agents: {list(all_results.keys())}")
        
        if "DeviceAnalyzerAgent" in all_results:
            result = all_results["DeviceAnalyzerAgent"]
            if result.get("status") == "success":
                insights = result.get("insights", {})
                device_count = insights.get("total_devices", 0)
                # Extract device types from by_type dictionary
                by_type = insights.get("by_type", {})
                if by_type:
                    device_types = set(by_type.keys())
                if device_count > 0:
                    has_devices = True
        
        if "TrendAnalyzerAgent" in all_results:
            result = all_results["TrendAnalyzerAgent"]
            if result.get("status") == "success":
                historical_data_points = result.get("data_point_count", 0)
                metrics_available = result.get("insights", {}).get("metrics", [])
                if historical_data_points > 0:
                    has_historical_data = True
                    has_realtime_data = True  # Historical data implies real-time capability

        # Build data availability summary and add to prompt
        prompt += f"""
## Data Availability Summary

**⚠️ CRITICAL: This summary is the SOURCE OF TRUTH for your report. Use these exact numbers.**

**Alarm Data**: {"⚠️ ✓ Available" if has_alarms else "✗ No alarms"} ({alarm_count} total, {critical_alarm_count} critical)
- **If the number above is > 0, alarms EXIST and you MUST mention them in Current Status**
- **If the number is 0, then you can say "No alarms detected"**

**Device Data**: {"✓ Available" if has_devices else "✗ No devices"} ({device_count} devices)
**Device Types**: {', '.join(device_types) if device_types else "Unknown"} {"(Single device type site)" if len(device_types) == 1 else "(Mixed device types)" if len(device_types) > 1 else ""}
**Real-time Data**: {"✓ Available" if has_realtime_data else "✗ Not available"}
**Historical Data**: {"✓ Available" if has_historical_data else "✗ Not available"} ({historical_data_points} data points)
**Metrics Available**: {', '.join(metrics_available) if metrics_available else "None"}

## Critical Analysis Requirements

Before generating the report, you MUST:

1. **Validate Data Availability**:
   - If no alarms exist, you CANNOT diagnose alarm-related issues
   - If only device registration exists (no operational data), acknowledge this limitation
   - If only one device type exists, consider this in your analysis (single-device sites have different characteristics)
   - If no historical data exists, you cannot identify trends or degradation

2. **Apply 5 Why Analysis**:
   For each potential issue identified:
   - Ask "Why did this happen?" (1st why)
   - Ask "Why did that occur?" (2nd why)
   - Continue until you reach the true root cause
   - Only include root causes that you can trace back through this analysis

3. **EMS Expert Perspective**:
   - Think systemically: How do devices interact? What are cascading effects?
   - Consider site context: Single device type vs. multi-device systems behave differently
   - Understand operational states: Device registration ≠ operational issues
   - Distinguish normal operation from actual problems

4. **Self-Validation Checklist** (apply to each section):
   - ✓ Is this statement correct based on the actual data provided?
   - ✓ Can a field engineer understand this without ambiguity?
   - ✓ Is this a specific, real problem or just generic/vague language?
   - ✓ Is this actionable? (Can someone actually do something about it?)
   - ✓ Am I fabricating problems that aren't in the data?

5. **Variable and Device Validation**:
   - Before mentioning any variable (e.g., SOC, temperature, voltage), verify:
     * Does this variable exist in the collected data?
     * Is it on the correct device type? (e.g., SOC should be on BMS devices, not PCS)
     * Is the device that should have this variable actually present?
   - If a variable is mentioned but doesn't exist in the data, state: "Variable X was not found in collected data"
   - If a variable exists on wrong device types, note this as a data quality issue
   - Understand variable relationships: Which variables influence others? Which are influenced?

6. **Honesty Requirements**:
   - **CRITICAL: Check the alarm count in "Data Availability Summary" - it is ACCURATE**
   - **If alarm_count > 0: You MUST state that alarms were detected and describe them (e.g., "X alarm(s) detected, including Y type")**
   - **If alarm_count = 0: State "No alarms detected, system appears to be operating normally"**
   - If only device registration: State "Devices are registered but insufficient operational data is available for comprehensive diagnosis"
   - If no historical data: State "Insufficient historical data to identify trends or degradation patterns"
   - If single device type: Acknowledge this in your analysis context
   - If variables are missing: State "Variable X is not available in collected data" instead of assuming it exists
   - Never invent problems like "Temperature Sensor Malfunction" unless temperature sensor alarms or data explicitly indicate this
   - **DO NOT ignore alarms if they are shown in the data availability summary**

## Report Generation Request

Generate a comprehensive diagnostic report for Site {site_id} using this format:
## Report Generation Request

Generate a comprehensive diagnostic report for Site {site_id} using this format:

## Current Status

[Write 2-3 sentences describing the overall site health. Be specific and clear.

**MANDATORY FORMAT - FOLLOW EXACTLY:**

1. **FIRST, check the "Data Availability Summary" section above - look for the line "Alarm Data: ✓ Available (X total, Y critical)"**

2. **If the summary shows "Alarm Data: ✓ Available" with a number > 0:**
   - **YOU MUST START with: "X alarm(s) detected" (where X is the exact number from the summary)**
   - **Then describe the alarm types from the "Alarm Analysis" section**
   - **Example: "1 alarm detected, related to cell_voltage_deviation. This suggests a potential issue with battery cell voltage readings that requires investigation."**
   - **DO NOT say "No alarms detected" if the summary shows alarms exist**

3. **If the summary shows "Alarm Data: ✗ No alarms" or count = 0:**
   - **Then you can say: "No alarms detected, system appears to be operating normally"**

4. **Additional context (if applicable):**
   - If only device registration: Mention "Devices are registered but insufficient operational data available"
   - If single device type: Mention this context
   - Be honest about what you know vs. what you don't know

**CRITICAL: The "Data Availability Summary" is the SOURCE OF TRUTH. If it shows alarms exist, you CANNOT say "No alarms detected" - this is a contradiction that will confuse readers.**]

## Risk Level

[Write: Low, Medium, or High]

[Write 1 sentence explaining why this risk level was assigned.
- Apply 5 Why analysis: Why is this the risk level? What evidence supports it?
- If no alarms and no issues found, the risk level MUST be Low
- If only device registration exists, risk is Low (registration ≠ operational issues)
- Be specific about what evidence led to this assessment]

## Root Causes

[CRITICAL: Apply rigorous analysis before listing root causes]

For each potential root cause, you MUST:
1. Verify it's supported by actual data (alarms, device status, trends)
2. Apply 5 Why analysis to trace back to the true root cause
3. Validate: Is this correct? Is this a real problem? Is this specific?
4. Only include if you can answer "yes" to all validation questions

[IMPORTANT: 
- **CRITICAL: Check alarm_count from "Data Availability Summary" - if > 0, alarms exist and you MUST analyze them**
- **If alarm_count > 0: Analyze the alarm types shown in "Alarm Analysis" section above and identify root causes**
- **If alarm_count = 0: State "No significant issues identified based on available data. No alarms detected."**
- If only device registration exists: State "Insufficient operational data available for root cause analysis. Devices are registered but no operational issues detected."
- If no historical data: State "Insufficient historical data to identify root causes related to trends or degradation."
- Do NOT invent problems like "Temperature Sensor Malfunction" unless temperature sensor alarms or data explicitly indicate this
- Do NOT use generic/vague root causes like "System needs monitoring" - be specific or state "No issues identified"
- **DO NOT ignore alarms - if they are shown in the data, they are real and need to be addressed**]

- [Only include root causes that pass the 5 Why and validation checks]
- [If no issues found, state: "No significant issues identified based on available data"]
- [Be specific: "Battery cell voltage deviation" not "System anomaly"]

## Recommended Actions

[CRITICAL: Only recommend actions that are:
1. Relevant to actual findings (not fabricated problems)
2. Actionable (someone can actually do this)
3. Specific (not vague like "monitor system")
4. Justified by the data]

[IMPORTANT:
- If no issues were found: Recommend "Continue normal operations and monitoring" or "No immediate action required"
- If only device registration: Recommend "Monitor device operational status as data becomes available"
- If insufficient data: Recommend "Collect more operational data for comprehensive analysis"
- Do NOT recommend actions for problems that were not identified
- Avoid generic recommendations - be specific or state "No actions required"]

- [Only include actions relevant to actual findings]
- [If no issues found, recommend: "Continue normal operations and monitoring"]
- [Be specific: "Check battery cell #5 voltage readings" not "Monitor batteries"]

## References

- [SOP reference if applicable and relevant to actual findings, otherwise omit this section]

## Final Self-Validation

Before finalizing this report, verify:
1. ✓ Every statement is supported by actual data
2. ✓ Every root cause has been validated through 5 Why analysis
3. ✓ Every recommendation is actionable and specific
4. ✓ No problems have been fabricated or assumed
5. ✓ Data limitations have been honestly acknowledged
6. ✓ The report reflects what the data actually shows, not what might be expected

Focus on accuracy, specificity, and actionable insights. Use clear, professional language. Be an EMS expert, not a generic AI assistant.
"""

        return prompt

    async def _parse_report(
        self, report_text: str, site_id: str, all_results: Dict[str, Dict[str, Any]]
    ) -> DiagnosticReport:
        """Parse LLM report into DiagnosticReport object"""
        # Extract risk level
        risk_level = self._extract_risk_level(report_text)

        # Extract current status
        current_status = self._extract_section(
            report_text, ["Current Status", "Status", "Site Status"]
        )

        # Extract root causes
        possible_causes = self._extract_list_section(
            report_text, ["Root Causes", "Root Cause", "Possible Causes", "Causes"]
        )

        # Extract recommended actions
        recommended_actions = self._extract_list_section(
            report_text,
            ["Recommended Actions", "Actions", "Recommendations", "Recommended Steps"],
        )

        # Extract references
        references = self._extract_list_section(
            report_text, ["References", "Reference", "SOP Reference"]
        )

        # Clean current_status using FormatterAgent
        cleaned_current_status = current_status or f"Diagnostic report for site {site_id}"
        if current_status:
            cleaned = await self.formatter.format_text(current_status)
            if cleaned:
                cleaned = cleaned.strip()
                # Remove any remaining ** or * symbols (extra safety)
                for _ in range(20):
                    cleaned = cleaned.replace('**', '')
                    cleaned = cleaned.replace('*', '')
                cleaned = cleaned.replace('`', '')
                cleaned_current_status = cleaned

        # Clean each list item using FormatterAgent
        cleaned_possible_causes = []
        for cause in possible_causes[:5]:
            cleaned = await self.formatter.format_text(cause)
            if cleaned and len(cleaned.strip()) > 3:
                cleaned_possible_causes.append(cleaned.strip())
        
        cleaned_recommended_actions = []
        for action in recommended_actions[:5]:
            cleaned = await self.formatter.format_text(action)
            if cleaned and len(cleaned.strip()) > 3:
                cleaned_recommended_actions.append(cleaned.strip())
        
        cleaned_references = []
        for ref in references:
            cleaned = await self.formatter.format_text(ref)
            if cleaned and len(cleaned.strip()) > 3:
                cleaned_references.append(cleaned.strip())

        # Generate alarm_id (use site_id for site-level diagnostic)
        alarm_id = f"site_{site_id}_diagnostic_{int(datetime.now(UTC).timestamp())}"

        return DiagnosticReport(
            alarm_id=alarm_id,
            current_status=cleaned_current_status,
            risk_level=risk_level,
            possible_causes=cleaned_possible_causes,
            recommended_actions=cleaned_recommended_actions,
            references=cleaned_references,
            generated_at=datetime.now(UTC),
            markdown=report_text,
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
        import re

        for section_name in section_names:
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
        """Extract list items from section
        
        Note: Formatting cleanup is handled by FormatterAgent, so we only do basic extraction here.
        """
        section_text = self._extract_section(text, section_names)
        if not section_text:
            return []

        items = []
        import re

        # Try to extract numbered or bulleted items
        patterns = [
            r"(?i)^\s*[0-9]+[\.\)]\s*(.+)$",  # Numbered: 1. item
            r"(?i)^\s*[-*•]\s*(.+)$",  # Bulleted: - item
        ]

        for line in section_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Skip headers
            if line.startswith('#'):
                continue
            
            # Skip section labels (basic check - FormatterAgent will handle detailed cleanup)
            line_lower = line.lower()
            if (line_lower.startswith('immediate action') or
                line_lower.startswith('short-term action') or
                line_lower.startswith('long-term action') or
                line_lower.startswith('action item')):
                continue
            
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    item = match.group(1).strip()
                    # Basic cleanup - just remove leading/trailing whitespace
                    item = item.strip()
                    if item and len(item) > 3:
                        items.append(item)
                    break

        return items

    def _create_fallback_report(
        self, site_id: str, all_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create fallback report when LLM fails"""
        # Determine risk level based on results
        has_critical = False
        has_warning = False

        if "AlarmAnalyzerAgent" in all_results:
            insights = all_results["AlarmAnalyzerAgent"].get("insights", {})
            if insights.get("critical_count", 0) > 0:
                has_critical = True
            if insights.get("total_alarms", 0) > 0:
                has_warning = True

        if has_critical:
            risk_level = RiskLevel.HIGH
        elif has_warning:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return {
            "alarm_id": f"site_{site_id}_diagnostic_{int(datetime.now(UTC).timestamp())}",
            "current_status": f"Diagnostic report generated for site {site_id}",
            "risk_level": risk_level.value,
            "possible_causes": ["System analysis completed", "Multiple data sources analyzed"],
            "recommended_actions": ["Review all analysis results", "Take appropriate actions based on findings"],
            "references": [],
        }

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Report generation completed"


