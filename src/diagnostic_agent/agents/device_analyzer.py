"""
Device Analyzer Agent
Analyzes device status and health
"""

import logging
from typing import Dict, Any, Optional, List

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class DeviceAnalyzerAgent(BaseDiagnosticAgent):
    """Agent for analyzing device status"""

    SYSTEM_PROMPT = """You are a device health analysis expert for BESS (Battery Energy Storage System) operations.

Your role is to analyze device data and identify:
1. Device health status (healthy, degraded, unhealthy)
2. Abnormal devices that need attention
3. Device performance issues
4. Device connectivity and status problems
5. Recommendations for device maintenance

Provide structured analysis with clear insights and actionable findings.
"""

    def __init__(self, llm_client: LLMClient):
        """Initialize device analyzer agent"""
        super().__init__(self.SYSTEM_PROMPT, llm_client, "DeviceAnalyzerAgent")

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Analyze device data"""
        site_id = context.get("site_id")

        # Get device data from dependencies
        device_data = None
        if dependencies:
            for dep in dependencies:
                dep_result = dep.get("result", {})
                if dep_result.get("data_type") == "devices":
                    device_data = dep_result.get("data", [])
                    break

        if not device_data:
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": "No device data available from dependencies",
                "site_id": site_id,
            }

        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(device_data, site_id)

            # Call LLM for analysis
            analysis_text = await self.llm_client.generate(prompt, self.system_prompt)

            # Extract structured insights
            insights = self._extract_insights(device_data, analysis_text)

            return {
                "status": "success",
                "agent": self.agent_name,
                "analysis": analysis_text,
                "insights": insights,
                "device_count": len(device_data),
                "site_id": site_id,
            }

        except Exception as e:
            logger.error(f"Device analysis failed: {e}", exc_info=True)
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": str(e),
                "site_id": site_id,
            }

    def _build_analysis_prompt(
        self, device_data: List[Dict[str, Any]], site_id: str
    ) -> str:
        """Build analysis prompt from device data"""
        prompt = f"""Analyze the device data for BESS Site {site_id}.

## Device Data Summary
Total Devices: {len(device_data)}

## Device Details
"""

        # Group devices by type and status
        by_type = {}
        by_status = {}

        for device in device_data[:50]:  # Limit to first 50 for prompt
            device_type = device.get("device_type", "unknown")
            status = device.get("status", "unknown")

            if device_type not in by_type:
                by_type[device_type] = 0
            by_type[device_type] += 1

            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

        prompt += "\n### Device Types Distribution:\n"
        for device_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            prompt += f"- {device_type}: {count} device(s)\n"

        prompt += "\n### Status Distribution:\n"
        for status, count in sorted(by_status.items(), key=lambda x: x[1], reverse=True):
            prompt += f"- {status}: {count} device(s)\n"

        # Show sample devices
        prompt += "\n### Sample Devices:\n"
        for i, device in enumerate(device_data[:5], 1):
            device_id = device.get("device_id", "unknown")
            device_type = device.get("device_type", "unknown")
            status = device.get("status", "unknown")
            last_seen = device.get("last_seen", "unknown")
            prompt += f"{i}. {device_id} ({device_type}) - Status: {status}, Last seen: {last_seen}\n"

        prompt += """
## Analysis Request
Please provide:
1. **Device Health Assessment**: Overall device health status
2. **Abnormal Devices**: Identify any devices with issues
3. **Status Issues**: Devices with connectivity or status problems
4. **Performance Analysis**: Device performance evaluation
5. **Recommendations**: Maintenance and action recommendations

Focus on actionable insights.
"""

        return prompt

    def _extract_insights(
        self, device_data: List[Dict[str, Any]], analysis_text: str
    ) -> Dict[str, Any]:
        """Extract structured insights from analysis"""
        # Count devices by type and status
        by_type = {}
        by_status = {}

        for device in device_data:
            device_type = device.get("device_type", "unknown")
            status = device.get("status", "unknown")

            if device_type not in by_type:
                by_type[device_type] = 0
            by_type[device_type] += 1

            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

        # Find unhealthy devices
        unhealthy_statuses = ["inactive", "offline", "error", "fault"]
        unhealthy_count = sum(
            count
            for status, count in by_status.items()
            if status.lower() in unhealthy_statuses
        )

        return {
            "total_devices": len(device_data),
            "by_type": by_type,
            "by_status": by_status,
            "unhealthy_count": unhealthy_count,
            "health_percentage": (
                ((len(device_data) - unhealthy_count) / len(device_data) * 100)
                if device_data
                else 0
            ),
        }

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Device analysis completed"

