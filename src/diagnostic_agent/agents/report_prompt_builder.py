"""
Report Prompt Builder
Builds the LLM prompt for diagnostic report generation from analysis results.
Used by ReportGeneratorAgent to build the prompt passed to the LLM.
"""

import logging
from typing import Any, Dict

from ...utils.debug import debug_print, is_debug_mode

logger = logging.getLogger(__name__)


def build_report_prompt(all_results: Dict[str, Dict[str, Any]], site_id: str) -> str:
    """Build report generation prompt from analysis results and site_id."""
    prompt = f"""Generate a comprehensive diagnostic report for BESS Site {site_id}.

**⚠️ CRITICAL INSTRUCTION BEFORE YOU START:**
- You will see a "Data Availability Summary" section below that shows the EXACT number of alarms
- If that number is > 0, you MUST mention alarms in the "Current Status" section
- DO NOT say "No alarms detected" if the summary shows alarms exist - this is a contradiction
- The alarm count in the summary is ACCURATE and comes directly from the analysis

## Analysis Results Summary
"""

    if "AlarmAnalyzerAgent" in all_results:
        result = all_results["AlarmAnalyzerAgent"]
        if result.get("status") == "success":
            prompt += "\n### Alarm Analysis:\n"
            analysis = result.get("analysis", "")
            if analysis:
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
                has_realtime_data = True

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

**CRITICAL: The "Data Availability Summary" is the SOURCE OF TRUTH. If it shows alarms exist, you CANNOT say "No alarms detected" - this is a contradiction that will confuse readers.**

**IMPORTANT: DO NOT include Risk Level or Why Analysis in Current Status section. Keep it concise - only 2-3 sentences about the current situation.**]

## Risk Level

[Write: Low, Medium, or High]

[Write 1 sentence explaining why this risk level was assigned.
- Apply 5 Why analysis internally (think through it), but DO NOT write out the analysis process
- If no alarms and no issues found, the risk level MUST be Low
- If only device registration exists, risk is Low (registration ≠ operational issues)
- Be specific about what evidence led to this assessment
- **IMPORTANT: Only include ONE "Risk Level" section. Do NOT create a separate "Risk Assessment" section. The risk level must be consistent throughout the report.**
- **DO NOT include "X Why Analysis" or analysis process in the output - only write the risk level and one sentence justification.**]

## Root Causes

[CRITICAL: Apply rigorous analysis before listing root causes]

For each potential root cause, you MUST:
1. Verify it's supported by actual data (alarms, device status, trends)
2. Apply 5 Why analysis internally to trace back to the true root cause (think through it, but DO NOT write out the analysis process)
3. Validate: Is this correct? Is this a real problem? Is this specific?
4. Only include if you can answer "yes" to all validation questions
5. **Write COMPLETE explanations, not just questions or titles**
6. **DO NOT include "Why did this happen?" questions or "X Why Analysis" sections - only write the final root cause statements**

[IMPORTANT: 
- **CRITICAL: Check alarm_count from "Data Availability Summary" - if > 0, alarms exist and you MUST analyze them**
- **If alarm_count > 0: Analyze the alarm types shown in "Alarm Analysis" section above and identify root causes**
- **If alarm_count = 0: State "No significant issues identified based on available data. No alarms detected."**
- If only device registration exists: State "Insufficient operational data available for root cause analysis. Devices are registered but no operational issues detected."
- If no historical data: State "Insufficient historical data to identify root causes related to trends or degradation."
- Do NOT invent problems like "Temperature Sensor Malfunction" unless temperature sensor alarms or data explicitly indicate this
- Do NOT use generic/vague root causes like "System needs monitoring" - be specific or state "No issues identified"
- **DO NOT ignore alarms - if they are shown in the data, they are real and need to be addressed**
- **DO NOT write "Why did X occur?" questions - provide the complete answer/explanation directly**
- **DO NOT include "5 Why Analysis" or analysis process in the output - only write the final root cause statements**
- **Each root cause must be a complete statement explaining the cause, not a question or analysis process**]

- [Only include root causes that pass the 5 Why and validation checks]
- [If no issues found, state: "No significant issues identified based on available data"]
- [Be specific: "Battery cell voltage deviation" not "System anomaly"]
- [Write complete explanations: "The BMS detected high SOC due to charging operations exceeding normal thresholds" not "Why did SOC become high?"]
- [Keep it concise - list 3-5 root causes, each as a single complete statement]

## Recommended Actions

[CRITICAL: Only recommend actions that are:
1. Relevant to actual findings (not fabricated problems)
2. Actionable (someone can actually do this)
3. Specific (not vague like "monitor system")
4. Justified by the data
5. **Complete and self-contained - each action must be a full sentence explaining what to do, not just a title or incomplete phrase**
6. **DO NOT include "X Why Analysis" or analysis process - only write the action statements**]

[IMPORTANT:
- If no issues were found: Recommend "Continue normal operations and monitoring" or "No immediate action required"
- If only device registration: Recommend "Monitor device operational status as data becomes available"
- If insufficient data: Recommend "Collect more operational data for comprehensive analysis"
- Do NOT recommend actions for problems that were not identified
- Avoid generic recommendations - be specific or state "No actions required"
- **DO NOT write incomplete actions like "Review and Confirm Current Conditions:" - write the complete action: "Review and confirm current conditions by verifying the actual state of charge (SOC) to ensure it is within expected operating parameters"**
- **Each action must be a complete, actionable statement that someone can follow without additional context**
- **DO NOT include analysis process or "Why Analysis" sections - only write the action statements**]

- [Only include actions relevant to actual findings]
- [If no issues found, recommend: "Continue normal operations and monitoring"]
- [Be specific: "Check battery cell #5 voltage readings" not "Monitor batteries"]
- [Write complete actions: "Review and confirm current conditions by verifying SOC levels are within normal operating range (20-80%)" not "Review and Confirm Current Conditions:"]
- [Keep it concise - list 3-5 actions, each as a single complete statement]

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
