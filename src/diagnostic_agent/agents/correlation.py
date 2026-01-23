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

    SYSTEM_PROMPT = """You are a correlation analysis expert for BESS (Battery Energy Storage System) operations.

Your role is to analyze multiple data sources and identify:
1. Correlations between alarms, devices, and trends
2. Root causes that affect multiple systems
3. Cascading failures and dependencies
4. System-wide patterns
5. Actionable insights for resolving issues

Provide structured analysis with clear correlations and root cause identification.
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

        prompt += """
## Correlation Analysis Request
Please provide:
1. **Correlations**: Relationships between alarms, devices, and trends
2. **Root Causes**: Identify potential root causes that affect multiple systems
3. **Cascading Effects**: Any cascading failures or dependencies
4. **System Patterns**: System-wide patterns and anomalies
5. **Actionable Insights**: Prioritized recommendations for resolving issues

Focus on identifying root causes and system-wide issues.
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







