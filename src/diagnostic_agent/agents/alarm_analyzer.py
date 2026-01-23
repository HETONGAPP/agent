"""
Alarm Analyzer Agent
Analyzes alarm patterns and trends
"""

import logging
from typing import Dict, Any, Optional, List

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class AlarmAnalyzerAgent(BaseDiagnosticAgent):
    """Agent for analyzing alarm patterns"""

    SYSTEM_PROMPT = """You are an alarm analysis expert for BESS (Battery Energy Storage System) operations.

Your role is to analyze alarm data and identify:
1. Alarm patterns (types, frequencies, distributions)
2. Severity distribution (Critical, Warning, Info)
3. Time trends (when alarms occur, frequency over time)
4. Critical issues that need immediate attention
5. Recurring problems

Provide structured analysis with clear insights and actionable findings.
"""

    def __init__(self, llm_client: LLMClient):
        """Initialize alarm analyzer agent"""
        super().__init__(self.SYSTEM_PROMPT, llm_client, "AlarmAnalyzerAgent")

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Analyze alarm data"""
        site_id = context.get("site_id")

        # Get alarm data from dependencies
        alarm_data = None
        if dependencies:
            for dep in dependencies:
                dep_result = dep.get("result", {})
                if dep_result.get("data_type") == "alarms":
                    alarm_data = dep_result.get("data", [])
                    break

        if not alarm_data:
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": "No alarm data available from dependencies",
                "site_id": site_id,
            }

        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(alarm_data, site_id)

            # Call LLM for analysis
            analysis_text = await self.llm_client.generate(prompt, self.system_prompt)

            # Extract structured insights
            insights = self._extract_insights(alarm_data, analysis_text)

            return {
                "status": "success",
                "agent": self.agent_name,
                "analysis": analysis_text,
                "insights": insights,
                "alarm_count": len(alarm_data),
                "site_id": site_id,
            }

        except Exception as e:
            logger.error(f"Alarm analysis failed: {e}", exc_info=True)
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": str(e),
                "site_id": site_id,
            }

    def _build_analysis_prompt(self, alarm_data: List[Dict[str, Any]], site_id: str) -> str:
        """Build analysis prompt from alarm data"""
        prompt = f"""Analyze the alarm data for BESS Site {site_id}.

## Alarm Data Summary
Total Alarms: {len(alarm_data)}

## Alarm Details
"""

        # Group alarms by type and severity
        by_type = {}
        by_severity = {"Critical": 0, "Warning": 0, "Info": 0}

        for alarm in alarm_data[:50]:  # Limit to first 50 for prompt
            alarm_type = alarm.get("alarm_type", "unknown")
            severity = alarm.get("severity", "unknown")

            if alarm_type not in by_type:
                by_type[alarm_type] = 0
            by_type[alarm_type] += 1

            if severity in by_severity:
                by_severity[severity] += 1

        prompt += "\n### Alarm Types Distribution:\n"
        for alarm_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]:
            prompt += f"- {alarm_type}: {count} occurrence(s)\n"

        prompt += "\n### Severity Distribution:\n"
        for severity, count in by_severity.items():
            prompt += f"- {severity}: {count} alarm(s)\n"

        # Show sample alarms
        prompt += "\n### Sample Alarms:\n"
        for i, alarm in enumerate(alarm_data[:5], 1):
            prompt += f"{i}. {alarm.get('alarm_type', 'unknown')} ({alarm.get('severity', 'unknown')}) "
            prompt += f"at {alarm.get('timestamp', 'unknown')}\n"

        prompt += """
## Analysis Request
Please provide:
1. **Pattern Analysis**: What patterns do you see in the alarms?
2. **Severity Assessment**: How critical is the situation?
3. **Time Trends**: Are there any time-based patterns?
4. **Critical Issues**: What are the most critical issues that need attention?
5. **Recommendations**: What actions should be taken?

Focus on actionable insights.
"""

        return prompt

    def _extract_insights(
        self, alarm_data: List[Dict[str, Any]], analysis_text: str
    ) -> Dict[str, Any]:
        """Extract structured insights from analysis"""
        # Count alarms by type and severity
        by_type = {}
        by_severity = {"Critical": 0, "Warning": 0, "Info": 0}

        for alarm in alarm_data:
            alarm_type = alarm.get("alarm_type", "unknown")
            severity = alarm.get("severity", "unknown")

            if alarm_type not in by_type:
                by_type[alarm_type] = 0
            by_type[alarm_type] += 1

            if severity in by_severity:
                by_severity[severity] += 1

        # Find most common alarm types
        most_common = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_alarms": len(alarm_data),
            "by_type": dict(most_common),
            "by_severity": by_severity,
            "most_common_type": most_common[0][0] if most_common else None,
            "critical_count": by_severity.get("Critical", 0),
        }

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Alarm analysis completed"

