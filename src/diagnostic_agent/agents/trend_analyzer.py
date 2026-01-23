"""
Trend Analyzer Agent
Analyzes historical trends and performance degradation
"""

import logging
from typing import Dict, Any, Optional, List, Set

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient
from ..variable_knowledge import (
    get_variable_info,
    get_related_variables,
    validate_variable_exists,
)

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

        if not historical_data or len(historical_data) == 0:
            # Return success with empty data message instead of error
            # This allows the report generator to handle the case gracefully
            return {
                "status": "success",
                "agent": self.agent_name,
                "analysis": "No historical time-series data available for analysis. This may indicate that the site is newly registered or devices have not yet started reporting data.",
                "insights": {
                    "total_points": 0,
                    "metrics": [],
                    "metric_count": 0,
                    "metric_stats": {},
                    "data_available": False,
                },
                "data_point_count": 0,
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
        """Build analysis prompt from historical data with variable validation"""
        prompt = f"""Analyze the historical time-series data for BESS Site {site_id}.

## Historical Data Summary
Total Data Points: {len(historical_data)}

## Data Overview
"""

        # Group data by metric, device, and validate variables
        by_metric = {}
        by_device = {}
        available_variables: Set[str] = set()
        available_devices: Dict[str, Dict[str, Any]] = {}
        variable_validations = {}

        for point in historical_data[:100]:  # Limit to first 100 for prompt
            metric = point.get("metric") or point.get("variable_name", "unknown")
            device_id = point.get("device_id", "unknown")
            device_type = point.get("device_type", "unknown")
            value = point.get("value")
            timestamp = point.get("timestamp", "unknown")

            # Track available variables and devices
            available_variables.add(metric.lower())
            if device_id not in available_devices:
                available_devices[device_id] = {
                    "device_id": device_id,
                    "device_type": device_type,
                    "status": point.get("device_status", "unknown"),
                }

            if metric not in by_metric:
                by_metric[metric] = []
            by_metric[metric].append({"value": value, "timestamp": timestamp, "device_id": device_id})

            if device_id not in by_device:
                by_device[device_id] = {"count": 0, "device_type": device_type}
            by_device[device_id]["count"] += 1

        # Validate variables and their associations
        prompt += "\n### Variable Validation and EMS System Context:\n"
        for metric in sorted(by_metric.keys()):
            var_info = get_variable_info(metric)
            if var_info:
                # Validate for each device that has this variable
                device_list = list(set([p.get("device_id") for p in by_metric[metric] if p.get("device_id")]))
                validation_results = []
                for device_id in device_list[:3]:  # Limit to 3 devices for prompt
                    device_info = available_devices.get(device_id, {})
                    validation = validate_variable_exists(
                        metric, device_id, device_info.get("device_type", ""),
                        available_variables, available_devices
                    )
                    validation_results.append(validation)
                
                valid_count = sum(1 for v in validation_results if v.get("exists", False))
                prompt += f"\n**{metric}** ({var_info.get('role', 'Unknown role')}):\n"
                prompt += f"- Description: {var_info.get('description', 'N/A')}\n"
                prompt += f"- Expected Device Types: {', '.join(var_info.get('device_types', []))}\n"
                prompt += f"- Related Variables: {', '.join(var_info.get('related_variables', [])[:5])}\n"
                prompt += f"- Influences: {', '.join(var_info.get('influences', [])[:3])}\n"
                prompt += f"- Influenced By: {', '.join(var_info.get('influenced_by', [])[:3])}\n"
                prompt += f"- Validation: {valid_count}/{len(validation_results)} devices have valid {metric} data\n"
            else:
                prompt += f"\n**{metric}**: Unknown variable (not in EMS knowledge base)\n"

        prompt += "\n### Metrics Available:\n"
        for metric, points in sorted(by_metric.items()):
            if points:
                values = [p["value"] for p in points if p["value"] is not None]
                if values:
                    avg_value = sum(values) / len(values)
                    min_value = min(values)
                    max_value = max(values)
                    device_count = len(set([p.get("device_id") for p in points]))
                    prompt += f"- {metric}: {len(points)} points from {device_count} device(s), avg={avg_value:.2f}, range=[{min_value:.2f}, {max_value:.2f}]\n"

        prompt += f"\n### Devices: {len(by_device)} device(s)\n"
        for device_id, info in list(by_device.items())[:5]:
            prompt += f"- {device_id} ({info.get('device_type', 'unknown')}): {info.get('count', 0)} data points\n"

        # Show sample data points with context
        prompt += "\n### Sample Data Points:\n"
        for i, point in enumerate(historical_data[:5], 1):
            metric = point.get("metric") or point.get("variable_name", "unknown")
            device_id = point.get("device_id", "unknown")
            device_type = point.get("device_type", "unknown")
            value = point.get("value", "N/A")
            timestamp = point.get("timestamp", "unknown")
            prompt += f"{i}. {metric} @ {device_id} ({device_type}): {value} (at {timestamp})\n"

        prompt += """
## Analysis Request

As an EMS expert, analyze the trends with these considerations:

1. **Variable Context**: Understand what each variable means in the EMS system:
   - What is its role? (e.g., SOC indicates battery capacity)
   - Which devices should have it? (e.g., SOC is from BMS devices)
   - What variables influence it? (e.g., SOC is influenced by current and active_power)
   - What does it influence? (e.g., SOC influences max_charge_power_limit)

2. **Device-Variable Validation**: 
   - Verify that variables exist on the correct device types
   - If a variable is missing from expected devices, note this as a data quality issue
   - If a variable appears on unexpected device types, investigate why

3. **Variable Relationships**:
   - Analyze how related variables interact (e.g., SOC, voltage, current, active_power)
   - Identify correlations between variables that should be related
   - Note when expected relationships are missing (data quality issue)

4. **Trend Analysis**: 
   - Overall trends for each metric (increasing, decreasing, stable)
   - Anomalies and unusual patterns
   - Degradation indicators (SOC, SOH, temperature trends)
   - Predictive insights about future performance

5. **Recommendations**: 
   - Actions based on trend analysis
   - Data quality improvements if variables are missing or on wrong devices
   - System health recommendations based on variable relationships

Focus on actionable insights, variable validation, and early warning signs.
"""

        return prompt

    def _extract_insights(
        self, historical_data: List[Dict[str, Any]], analysis_text: str
    ) -> Dict[str, Any]:
        """Extract structured insights from analysis with variable validation"""
        # Group by metric and device
        by_metric = {}
        by_device = {}
        available_variables: Set[str] = set()
        available_devices: Dict[str, Dict[str, Any]] = {}

        for point in historical_data:
            metric = point.get("metric") or point.get("variable_name", "unknown")
            device_id = point.get("device_id", "unknown")
            device_type = point.get("device_type", "unknown")
            value = point.get("value")
            
            available_variables.add(metric.lower())
            if device_id not in available_devices:
                available_devices[device_id] = {
                    "device_id": device_id,
                    "device_type": device_type,
                    "status": point.get("device_status", "unknown"),
                }
            
            if metric not in by_metric:
                by_metric[metric] = []
            if value is not None:
                by_metric[metric].append(value)
            
            if device_id not in by_device:
                by_device[device_id] = {"metrics": set(), "count": 0}
            by_device[device_id]["metrics"].add(metric)
            by_device[device_id]["count"] += 1

        # Calculate basic statistics
        metric_stats = {}
        variable_validations = {}
        for metric, values in by_metric.items():
            if values:
                metric_stats[metric] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
                # Validate variable
                var_info = get_variable_info(metric)
                if var_info:
                    # Check which devices have this variable
                    devices_with_var = [
                        device_id for device_id, info in by_device.items()
                        if metric in info.get("metrics", set())
                    ]
                    valid_devices = []
                    for device_id in devices_with_var:
                        device_info = available_devices.get(device_id, {})
                        validation = validate_variable_exists(
                            metric, device_id, device_info.get("device_type", ""),
                            available_variables, available_devices
                        )
                        if validation.get("exists", False):
                            valid_devices.append(device_id)
                    
                    variable_validations[metric] = {
                        "valid_device_count": len(valid_devices),
                        "total_device_count": len(devices_with_var),
                        "variable_info": {
                            "role": var_info.get("role"),
                            "device_types": var_info.get("device_types", []),
                        }
                    }

        return {
            "total_points": len(historical_data),
            "metrics": list(by_metric.keys()),
            "metric_count": len(by_metric),
            "metric_stats": metric_stats,
            "variable_validations": variable_validations,
            "device_count": len(by_device),
        }

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Trend analysis completed"







