"""
Correlation Agent
Discovers correlations between different data sources
"""

import logging
from typing import Dict, Any, Optional, List

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class CorrelationAgent(BaseDiagnosticAgent):
    """Agent for discovering correlations between data sources"""

    SYSTEM_PROMPT = """You are an EMS (Energy Management System) expert and correlation analysis specialist for BESS (Battery Energy Storage System) operations.

Your role is to analyze multiple data sources and identify meaningful correlations, root causes, and system-wide patterns.

## Your Expertise
- You have deep knowledge of BESS system architecture, device interactions, and energy management
- You think like an experienced field engineer who understands how different system components interact
- You apply rigorous analysis: ask "why" multiple times (5 Why method) to get to true root causes
- You validate your conclusions: Is this correct? Can I understand it? Is this a real correlation? Is this actionable?

## Analysis Principles
1. **Data Validation**: Before identifying correlations, verify:
   - Are there actual alarms to correlate?
   - Are there multiple devices or just one device type?
   - Is there real operational data or just device registration?
   - Is there historical data showing trends?

2. **EMS Expert Perspective**: 
   - Understand system-level interactions: How do BMS, PCS, EMS interact?
   - Recognize that single device type sites have different correlation patterns
   - Distinguish between correlation and causation
   - Consider cascading effects and dependencies

3. **5 Why Analysis**: For each correlation or root cause:
   - Why do these correlate? (1st why)
   - Why does that relationship exist? (2nd why)
   - Continue until reaching the true underlying cause

4. **Self-Validation**: Before finalizing conclusions:
   - Is this correlation real or coincidental?
   - Can a field engineer understand and act on this?
   - Is this a specific, actionable insight or just generic observation?
   - Am I fabricating relationships that aren't in the data?

5. **Honesty About Limitations**:
   - If no alarms exist, you cannot correlate alarms with other data
   - If only device registration exists, acknowledge limited correlation analysis possible
   - If only one device type exists, note this in your analysis
   - Never invent correlations that aren't supported by the data

Provide structured analysis with clear, validated correlations and root cause identification. Be specific and actionable.
"""

    def __init__(self, llm_client: LLMClient):
        """Initialize correlation agent"""
        super().__init__(self.SYSTEM_PROMPT, llm_client, "CorrelationAgent")

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Analyze correlations between different data sources"""
        site_id = context.get("site_id")

        # Collect results from all dependency tasks
        alarm_analysis = None
        device_analysis = None
        trend_analysis = None

        if dependencies:
            for dep in dependencies:
                dep_result = dep.get("result", {})
                agent = dep_result.get("agent", "")
                
                if agent == "AlarmAnalyzerAgent":
                    alarm_analysis = dep_result
                elif agent == "DeviceAnalyzerAgent":
                    device_analysis = dep_result
                elif agent == "TrendAnalyzerAgent":
                    trend_analysis = dep_result

        if not alarm_analysis and not device_analysis and not trend_analysis:
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": "No analysis results available from dependencies",
                "site_id": site_id,
            }

        try:
            # Build correlation analysis prompt
            prompt = self._build_correlation_prompt(
                alarm_analysis, device_analysis, trend_analysis, site_id
            )

            # Call LLM for correlation analysis
            analysis_text = await self.llm_client.generate(prompt, self.system_prompt)

            # Extract structured correlations
            correlations = self._extract_correlations(
                alarm_analysis, device_analysis, trend_analysis, analysis_text
            )

            return {
                "status": "success",
                "agent": self.agent_name,
                "analysis": analysis_text,
                "correlations": correlations,
                "site_id": site_id,
            }

        except Exception as e:
            logger.error(f"Correlation analysis failed: {e}", exc_info=True)
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": str(e),
                "site_id": site_id,
            }

    def _build_correlation_prompt(
        self,
        alarm_analysis: Optional[Dict[str, Any]],
        device_analysis: Optional[Dict[str, Any]],
        trend_analysis: Optional[Dict[str, Any]],
        site_id: str,
    ) -> str:
        """Build correlation analysis prompt"""
        prompt = f"""Analyze correlations between different data sources for BESS Site {site_id}.

## Available Analysis Results
"""

        if alarm_analysis:
            prompt += "\n### Alarm Analysis Results:\n"
            if alarm_analysis.get("status") == "success":
                insights = alarm_analysis.get("insights", {})
                prompt += f"- Total Alarms: {insights.get('total_alarms', 0)}\n"
                prompt += f"- Critical Alarms: {insights.get('critical_count', 0)}\n"
                prompt += f"- Most Common Type: {insights.get('most_common_type', 'N/A')}\n"
                analysis = alarm_analysis.get("analysis", "")
                if analysis:
                    preview = analysis[:200] + "..." if len(analysis) > 200 else analysis
                    prompt += f"- Analysis Preview: {preview}\n"
            else:
                prompt += "- Status: Error or unavailable\n"

        if device_analysis:
            prompt += "\n### Device Analysis Results:\n"
            if device_analysis.get("status") == "success":
                insights = device_analysis.get("insights", {})
                prompt += f"- Total Devices: {insights.get('total_devices', 0)}\n"
                prompt += f"- Unhealthy Devices: {insights.get('unhealthy_count', 0)}\n"
                prompt += f"- Health Percentage: {insights.get('health_percentage', 0):.1f}%\n"
                analysis = device_analysis.get("analysis", "")
                if analysis:
                    preview = analysis[:200] + "..." if len(analysis) > 200 else analysis
                    prompt += f"- Analysis Preview: {preview}\n"
            else:
                prompt += "- Status: Error or unavailable\n"

        if trend_analysis:
            prompt += "\n### Trend Analysis Results:\n"
            if trend_analysis.get("status") == "success":
                insights = trend_analysis.get("insights", {})
                prompt += f"- Data Points: {insights.get('total_points', 0)}\n"
                prompt += f"- Metrics Analyzed: {', '.join(insights.get('metrics', []))}\n"
                analysis = trend_analysis.get("analysis", "")
                if analysis:
                    preview = analysis[:200] + "..." if len(analysis) > 200 else analysis
                    prompt += f"- Analysis Preview: {preview}\n"
            else:
                prompt += "- Status: Error or unavailable\n"

        # Extract detailed data availability
        has_alarms = False
        alarm_count = 0
        has_devices = False
        device_count = 0
        device_types = set()
        has_historical_data = False
        data_points = 0
        
        if alarm_analysis and alarm_analysis.get("status") == "success":
            insights = alarm_analysis.get("insights", {})
            alarm_count = insights.get("total_alarms", 0)
            if alarm_count > 0:
                has_alarms = True
        
        if device_analysis and device_analysis.get("status") == "success":
            insights = device_analysis.get("insights", {})
            device_count = insights.get("total_devices", 0)
            # Extract device types from by_type dictionary
            by_type = insights.get("by_type", {})
            if by_type:
                device_types = set(by_type.keys())
            if device_count > 0:
                has_devices = True
        
        if trend_analysis and trend_analysis.get("status") == "success":
            data_points = trend_analysis.get("data_point_count", 0)
            if data_points > 0:
                has_historical_data = True

        prompt += f"""
## Data Availability for Correlation Analysis

**Alarm Data**: {"✓ Available" if has_alarms else "✗ No alarms"} ({alarm_count} alarms)
**Device Data**: {"✓ Available" if has_devices else "✗ No devices"} ({device_count} devices)
**Device Types**: {', '.join(device_types) if device_types else "Unknown"} {"(Single device type - limited correlation analysis)" if len(device_types) == 1 else "(Multiple device types - full correlation possible)" if len(device_types) > 1 else ""}
**Historical Data**: {"✓ Available" if has_historical_data else "✗ Not available"} ({data_points} data points)

## Correlation Analysis Request

As an EMS expert, analyze correlations with these requirements:

1. **Data Validation First**:
   - If no alarms exist, you CANNOT correlate alarms with other data
   - If only device registration exists (no operational data), acknowledge this limitation
   - If only one device type exists, note that correlation analysis is limited
   - Only identify correlations that are supported by actual data

2. **Apply 5 Why Analysis**:
   For each correlation identified:
   - Why do these correlate? (1st why)
   - Why does that relationship exist? (2nd why)
   - Why does that underlying cause exist? (3rd why)
   - Continue until reaching the true root cause
   - Only include correlations that pass this validation

3. **EMS Expert Perspective**:
   - Think systemically: How do BMS, PCS, EMS, and other devices interact?
   - Consider cascading effects: If one system fails, what else is affected?
   - Understand device dependencies: Which devices depend on others?
   - Recognize single-device-type limitations: Less correlation possible

4. **Self-Validation Checklist**:
   - ✓ Is this correlation real or just coincidental?
   - ✓ Can a field engineer understand this relationship?
   - ✓ Is this a specific, actionable insight or generic observation?
   - ✓ Am I fabricating correlations that aren't in the data?

5. **Provide Structured Analysis**:
   - **Correlations**: Real relationships between alarms, devices, and trends (only if data supports)
   - **Root Causes**: True root causes affecting multiple systems (validated through 5 Why)
   - **Cascading Effects**: Actual cascading failures or dependencies (not assumed)
   - **System Patterns**: Real system-wide patterns (not generic observations)
   - **Actionable Insights**: Specific, prioritized recommendations (not vague suggestions)

6. **Honesty Requirements**:
   - If no alarms: State "No alarm correlations possible - no alarms detected"
   - If only device registration: State "Limited correlation analysis - insufficient operational data"
   - If single device type: Note "Single device type site - limited inter-device correlation analysis"
   - If no historical data: State "No trend correlations possible - insufficient historical data"
   - Never invent correlations that aren't supported by the data

Focus on identifying validated root causes and system-wide issues. Be specific, actionable, and honest about limitations.
"""

        return prompt

    def _extract_correlations(
        self,
        alarm_analysis: Optional[Dict[str, Any]],
        device_analysis: Optional[Dict[str, Any]],
        trend_analysis: Optional[Dict[str, Any]],
        analysis_text: str,
    ) -> Dict[str, Any]:
        """Extract structured correlations"""
        correlations = {
            "has_alarm_data": alarm_analysis is not None and alarm_analysis.get("status") == "success",
            "has_device_data": device_analysis is not None and device_analysis.get("status") == "success",
            "has_trend_data": trend_analysis is not None and trend_analysis.get("status") == "success",
        }

        # Extract key metrics from each analysis
        if alarm_analysis and alarm_analysis.get("status") == "success":
            insights = alarm_analysis.get("insights", {})
            correlations["alarm_metrics"] = {
                "total": insights.get("total_alarms", 0),
                "critical": insights.get("critical_count", 0),
            }

        if device_analysis and device_analysis.get("status") == "success":
            insights = device_analysis.get("insights", {})
            correlations["device_metrics"] = {
                "total": insights.get("total_devices", 0),
                "unhealthy": insights.get("unhealthy_count", 0),
                "health_percentage": insights.get("health_percentage", 0),
            }

        if trend_analysis and trend_analysis.get("status") == "success":
            insights = trend_analysis.get("insights", {})
            correlations["trend_metrics"] = {
                "data_points": insights.get("total_points", 0),
                "metrics": insights.get("metrics", []),
            }

        return correlations

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Correlation analysis completed"







