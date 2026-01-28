"""
Report Generator Agent
Generates comprehensive diagnostic reports
"""

import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient
from ...models.diagnostic import DiagnosticReport, RiskLevel
from .formatter import FormatterAgent
from .report_parser import ReportParser
from .report_prompt_builder import build_report_prompt
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
        self.formatter = FormatterAgent(llm_client)
        self.report_parser = ReportParser()

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
            prompt = build_report_prompt(all_results, site_id)

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

    async def _parse_report(
        self, report_text: str, site_id: str, all_results: Dict[str, Dict[str, Any]]
    ) -> DiagnosticReport:
        """Parse LLM report into DiagnosticReport object"""
        risk_level = self.report_parser.extract_risk_level(report_text)
        current_status = self.report_parser.extract_section(
            report_text, ["Current Status", "Status", "Site Status"]
        )
        possible_causes = self.report_parser.extract_list_section(
            report_text, ["Root Causes", "Root Cause", "Possible Causes", "Causes"]
        )
        recommended_actions = self.report_parser.extract_list_section(
            report_text,
            ["Recommended Actions", "Actions", "Recommendations", "Recommended Steps"],
        )
        references = self.report_parser.extract_list_section(
            report_text, ["References", "Reference", "SOP Reference"]
        )

        # Clean current_status using FormatterAgent
        cleaned_current_status = current_status or f"Diagnostic report for site {site_id}"
        if current_status:
            # Remove analysis process content (Why Analysis, Risk Level mentions, etc.)
            import re
            # Remove "X Why Analysis" patterns
            current_status = re.sub(r'\d+\s+Why\s+Analysis[:\-]?\s*', '', current_status, flags=re.IGNORECASE)
            # Remove "Risk Level" mentions from Current Status
            current_status = re.sub(r'-?\s*Risk\s+Level\s+(Low|Medium|High).*?\.', '', current_status, flags=re.IGNORECASE | re.DOTALL)
            # Remove lines starting with "-" that contain analysis process
            lines = current_status.split('\n')
            cleaned_lines = []
            for line in lines:
                line_stripped = line.strip()
                # Skip lines that are analysis process indicators
                if re.search(r'(Why\s+Analysis|Why\s+did|Why\s+is)', line_stripped, re.IGNORECASE):
                    continue
                cleaned_lines.append(line)
            current_status = '\n'.join(cleaned_lines)
            
            cleaned = await self.formatter.format_text(current_status)
            if cleaned:
                cleaned = cleaned.strip()
                # Remove any remaining ** or * symbols (extra safety)
                for _ in range(20):
                    cleaned = cleaned.replace('**', '')
                    cleaned = cleaned.replace('*', '')
                cleaned = cleaned.replace('`', '')
                # Remove any remaining analysis process mentions
                cleaned = re.sub(r'\d+\s+Why\s+Analysis[:\-]?\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned_current_status = cleaned

        # Clean each list item using FormatterAgent
        cleaned_possible_causes = []
        import re
        for cause in possible_causes[:5]:
            # Remove analysis process content
            cause = re.sub(r'Why\s+did\s+(this|that|it)\s+happen\?[:\-]?\s*', '', cause, flags=re.IGNORECASE)
            cause = re.sub(r'Why\s+did\s+(this|that|it)\s+occur\?[:\-]?\s*', '', cause, flags=re.IGNORECASE)
            cause = re.sub(r'Why\s+is\s+this\s+happening\?[:\-]?\s*', '', cause, flags=re.IGNORECASE)
            cause = re.sub(r'\d+\s+Why\s+Analysis[:\-]?\s*', '', cause, flags=re.IGNORECASE)
            # Remove question-answer format, keep only the answer
            cause = re.sub(r'^Why\s+.*?\?\s*[-:]?\s*', '', cause, flags=re.IGNORECASE | re.MULTILINE)
            
            cleaned = await self.formatter.format_text(cause)
            if cleaned and len(cleaned.strip()) > 3:
                cleaned = cleaned.strip()
                # Remove any remaining analysis process mentions
                cleaned = re.sub(r'Why\s+did.*?\?\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'\d+\s+Why\s+Analysis[:\-]?\s*', '', cleaned, flags=re.IGNORECASE)
                if cleaned and len(cleaned) > 10:  # Ensure it's a complete statement
                    cleaned_possible_causes.append(cleaned)
        
        cleaned_recommended_actions = []
        for action in recommended_actions[:5]:
            # Remove analysis process content
            action = re.sub(r'\d+\s+Why\s+Analysis[:\-]?\s*', '', action, flags=re.IGNORECASE)
            # Remove explanation lines that start with "-" and contain analysis
            lines = action.split('\n')
            cleaned_lines = []
            for line in lines:
                line_stripped = line.strip()
                # Skip lines that are analysis explanations
                if re.search(r'(Why\s+Analysis|ensures|helps|will provide)', line_stripped, re.IGNORECASE) and line_stripped.startswith('-'):
                    continue
                cleaned_lines.append(line)
            action = '\n'.join(cleaned_lines)
            
            cleaned = await self.formatter.format_text(action)
            if cleaned and len(cleaned.strip()) > 3:
                cleaned = cleaned.strip()
                # Remove any remaining analysis process mentions
                cleaned = re.sub(r'\d+\s+Why\s+Analysis[:\-]?\s*', '', cleaned, flags=re.IGNORECASE)
                # Remove explanation sentences that are analysis process
                sentences = re.split(r'[\.!?]\s+', cleaned)
                action_sentences = []
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence and not re.search(r'(ensures|helps|will provide|because|due to)', sentence.lower()):
                        action_sentences.append(sentence)
                    elif sentence and len(sentence.split()) > 5:  # Keep longer sentences that might be actual actions
                        action_sentences.append(sentence)
                if action_sentences:
                    cleaned = '. '.join(action_sentences).strip()
                    if cleaned and len(cleaned) > 10:
                        cleaned_recommended_actions.append(cleaned)
                elif cleaned and len(cleaned) > 10:
                    cleaned_recommended_actions.append(cleaned)
        
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


