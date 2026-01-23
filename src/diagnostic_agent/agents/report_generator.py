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

logger = logging.getLogger(__name__)


class ReportGeneratorAgent(BaseDiagnosticAgent):
    """Agent for generating comprehensive diagnostic reports"""

    SYSTEM_PROMPT = """You are a diagnostic report generation expert for BESS (Battery Energy Storage System) operations.

Your role is to synthesize all analysis results into a comprehensive diagnostic report.

Generate a professional, structured diagnostic report with these exact sections:
1. Current Status: Overall site health assessment (2-3 sentences)
2. Risk Level: Low/Medium/High with brief justification
3. Root Causes: Bullet list of identified root causes (3-5 items)
4. Recommended Actions: Bullet list of prioritized actions (3-5 items)
5. References: Bullet list of SOP references if applicable

Use clear, professional language. Focus on accuracy and actionable insights.
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

        # Collect all analysis results from dependencies
        all_results = {}
        if dependencies:
            for dep in dependencies:
                dep_result = dep.get("result", {})
                agent = dep_result.get("agent", "")
                if agent:
                    all_results[agent] = dep_result

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

## Analysis Results Summary
"""

        # Include all analysis results
        if "AlarmAnalyzerAgent" in all_results:
            result = all_results["AlarmAnalyzerAgent"]
            if result.get("status") == "success":
                prompt += "\n### Alarm Analysis:\n"
                analysis = result.get("analysis", "")
                if analysis:
                    preview = analysis[:300] + "..." if len(analysis) > 300 else analysis
                    prompt += f"{preview}\n"
                insights = result.get("insights", {})
                prompt += f"- Total Alarms: {insights.get('total_alarms', 0)}\n"
                prompt += f"- Critical Alarms: {insights.get('critical_count', 0)}\n"

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

        if "CorrelationAgent" in all_results:
            result = all_results["CorrelationAgent"]
            if result.get("status") == "success":
                prompt += "\n### Correlation Analysis:\n"
                analysis = result.get("analysis", "")
                if analysis:
                    preview = analysis[:300] + "..." if len(analysis) > 300 else analysis
                    prompt += f"{preview}\n"

        prompt += f"""
## Report Generation Request

Generate a comprehensive diagnostic report for Site {site_id} using this format:

## Current Status

[Write 2-3 sentences describing the overall site health. Be specific and clear.]

## Risk Level

[Write: Low, Medium, or High]

[Write 1 sentence explaining why this risk level was assigned.]

## Root Causes

- [First root cause: one clear sentence]
- [Second root cause: one clear sentence]
- [Third root cause: one clear sentence]

## Recommended Actions

- [First action: one clear, actionable sentence]
- [Second action: one clear, actionable sentence]
- [Third action: one clear, actionable sentence]

## References

- [SOP reference if applicable, otherwise omit this section]

Focus on accuracy, clarity, and actionable insights. Use clear, professional language.
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


