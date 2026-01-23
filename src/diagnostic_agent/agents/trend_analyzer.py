"""
Trend Analyzer Agent
Analyzes historical trends and performance degradation
"""

import logging
from typing import Dict, Any, Optional, List

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class TrendAnalyzerAgent(BaseDiagnosticAgent):
    """Agent for analyzing historical trends"""

    SYSTEM_PROMPT = """You are a trend analysis expert for BESS (Battery Energy Storage System) operations.

Your role is to analyze historical time-series data and identify:
1. Performance trends (improving, stable, degrading)
2. Anomalies and unusual patterns
3. Degradation indicators (SOC, SOH, temperature trends)
4. Predictive insights
5. Recommendations based on trends

Provide structured analysis with clear insights and actionable findings.
"""

    def __init__(self, llm_client: LLMClient):
        """Initialize trend analyzer agent"""
        super().__init__(self.SYSTEM_PROMPT, llm_client, "TrendAnalyzerAgent")

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Analyze historical trend data"""
        site_id = context.get("site_id")

        # Get historical data from dependencies
        historical_data = None
        if dependencies:
            for dep in dependencies:
                dep_result = dep.get("result", {})
                if dep_result.get("data_type") == "historical":
                    historical_data = dep_result.get("data", [])
                    break

        if not historical_data:
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": "No historical data available from dependencies",
                "site_id": site_id,
            }

        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(historical_data, site_id)

            # Call LLM for analysis
            analysis_text = await self.llm_client.generate(prompt, self.system_prompt)

            # Extract structured insights
            insights = self._extract_insights(historical_data, analysis_text)

            return {
                "status": "success",
                "agent": self.agent_name,
                "analysis": analysis_text,
                "insights": insights,
                "data_point_count": len(historical_data),
                "site_id": site_id,
            }

        except Exception as e:
            logger.error(f"Trend analysis failed: {e}", exc_info=True)
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": str(e),
                "site_id": site_id,
            }

    def _build_analysis_prompt(
        self, historical_data: List[Dict[str, Any]], site_id: str
    ) -> str:
        """Build analysis prompt from historical data"""
        prompt = f"""Analyze the historical time-series data for BESS Site {site_id}.

## Historical Data Summary
Total Data Points: {len(historical_data)}

## Data Overview
"""

        # Group data by metric
        by_metric = {}
        by_device = {}

        for point in historical_data[:100]:  # Limit to first 100 for prompt
            metric = point.get("metric", "unknown")
            device_id = point.get("device_id", "unknown")
            value = point.get("value")
            timestamp = point.get("timestamp", "unknown")

            if metric not in by_metric:
                by_metric[metric] = []
            by_metric[metric].append({"value": value, "timestamp": timestamp})

            if device_id not in by_device:
                by_device[device_id] = 0
            by_device[device_id] += 1

        prompt += "\n### Metrics Available:\n"
        for metric, points in sorted(by_metric.items()):
            if points:
                values = [p["value"] for p in points if p["value"] is not None]
                if values:
                    avg_value = sum(values) / len(values)
                    min_value = min(values)
                    max_value = max(values)
                    prompt += f"- {metric}: {len(points)} points, avg={avg_value:.2f}, range=[{min_value:.2f}, {max_value:.2f}]\n"

        prompt += f"\n### Devices: {len(by_device)} device(s)\n"

        # Show sample data points
        prompt += "\n### Sample Data Points:\n"
        for i, point in enumerate(historical_data[:5], 1):
            metric = point.get("metric", "unknown")
            device_id = point.get("device_id", "unknown")
            value = point.get("value", "N/A")
            timestamp = point.get("timestamp", "unknown")
            prompt += f"{i}. {metric} @ {device_id}: {value} (at {timestamp})\n"

        prompt += """
## Analysis Request
Please provide:
1. **Trend Analysis**: Overall trends for each metric (increasing, decreasing, stable)
2. **Anomalies**: Identify any unusual patterns or outliers
3. **Degradation Indicators**: Signs of performance degradation
4. **Predictive Insights**: What the trends suggest about future performance
5. **Recommendations**: Actions based on trend analysis

Focus on actionable insights and early warning signs.
"""

        return prompt

    def _extract_insights(
        self, historical_data: List[Dict[str, Any]], analysis_text: str
    ) -> Dict[str, Any]:
        """Extract structured insights from analysis"""
        # Group by metric
        by_metric = {}
        for point in historical_data:
            metric = point.get("metric", "unknown")
            value = point.get("value")
            if metric not in by_metric:
                by_metric[metric] = []
            if value is not None:
                by_metric[metric].append(value)

        # Calculate basic statistics
        metric_stats = {}
        for metric, values in by_metric.items():
            if values:
                metric_stats[metric] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }

        return {
            "total_points": len(historical_data),
            "metrics": list(by_metric.keys()),
            "metric_count": len(by_metric),
            "metric_stats": metric_stats,
        }

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Trend analysis completed"







