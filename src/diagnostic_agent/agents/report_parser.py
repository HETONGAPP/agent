"""
Report Parser
Extracts structured sections and risk level from diagnostic report text.
Used by ReportGeneratorAgent to parse LLM output into DiagnosticReport fields.
"""

import re
from typing import List, Optional

from ...models.diagnostic import RiskLevel


class ReportParser:
    """Parses raw report text into sections and risk level. No LLM or formatter dependency."""

    # Section headers that terminate extraction (used by extract_section)
    KNOWN_SECTIONS = [
        "Current Status", "Status", "Site Status",
        "Risk Level", "Risk Assessment",
        "Root Causes", "Root Cause", "Possible Causes", "Causes",
        "Recommended Actions", "Actions", "Recommendations", "Recommended Steps",
        "References", "Reference", "SOP Reference",
        "Final Self-Validation", "Self-Validation",
    ]

    def extract_risk_level(self, text: str) -> RiskLevel:
        """
        Extract risk level from text.
        Prioritizes "Risk Level" section over "Risk Assessment" section.
        """
        risk_level_section = self.extract_section(text, ["Risk Level", "Risk"])
        if risk_level_section:
            risk_level_text = risk_level_section.lower()
            if "high" in risk_level_text and "risk" in risk_level_text:
                return RiskLevel.HIGH
            elif "medium" in risk_level_text and "risk" in risk_level_text:
                return RiskLevel.MEDIUM
            elif "low" in risk_level_text and "risk" in risk_level_text:
                return RiskLevel.LOW
            if re.search(r'\b(high|medium|low)\b', risk_level_text):
                if "high" in risk_level_text:
                    return RiskLevel.HIGH
                elif "medium" in risk_level_text:
                    return RiskLevel.MEDIUM
                elif "low" in risk_level_text:
                    return RiskLevel.LOW

        risk_assessment_section = self.extract_section(text, ["Risk Assessment"])
        if risk_assessment_section:
            assessment_text = risk_assessment_section.lower()
            if "high" in assessment_text and "risk" in assessment_text:
                return RiskLevel.HIGH
            elif "medium" in assessment_text and "risk" in assessment_text:
                return RiskLevel.MEDIUM
            elif "low" in assessment_text and "risk" in assessment_text:
                return RiskLevel.LOW
            if re.search(r'\b(high|medium|low)\b', assessment_text):
                if "high" in assessment_text:
                    return RiskLevel.HIGH
                elif "medium" in assessment_text:
                    return RiskLevel.MEDIUM
                elif "low" in assessment_text:
                    return RiskLevel.LOW

        text_lower = text.lower()
        risk_level_patterns = [
            r'(?i)risk\s+level[:\-]?\s*(high|medium|low)',
            r'(?i)risk\s+level[:\-]?\s*is\s*(high|medium|low)',
        ]
        for pattern in risk_level_patterns:
            match = re.search(pattern, text)
            if match:
                level = match.group(1).lower()
                if level == "high":
                    return RiskLevel.HIGH
                elif level == "medium":
                    return RiskLevel.MEDIUM
                elif level == "low":
                    return RiskLevel.LOW

        if any(w in text_lower for w in ["critical", "urgent", "severe", "danger"]) and "risk" in text_lower:
            return RiskLevel.HIGH
        if any(w in text_lower for w in ["warning", "caution", "moderate"]) and "risk" in text_lower:
            return RiskLevel.MEDIUM
        if "low" in text_lower and "risk" in text_lower:
            return RiskLevel.LOW
        return RiskLevel.LOW

    def extract_section(self, text: str, section_names: List[str]) -> Optional[str]:
        """
        Extract section content from text until the next ## header or end of text.
        """
        for section_name in section_names:
            pattern1 = rf"(?i){re.escape(section_name)}[:\-]?\s*\n(.*?)(?=\n##\s+[A-Z]|\Z)"
            pattern2 = rf"(?i){re.escape(section_name)}[:\-]?\s*(.*?)(?=\n##\s+[A-Z]|\Z)"
            for pattern in [pattern1, pattern2]:
                match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
                if match:
                    content = match.group(1).strip()
                    if content:
                        lines = content.split('\n')
                        cleaned_lines = []
                        for line in lines:
                            line_stripped = line.strip()
                            if any(line_stripped.startswith(f"## {s}") or line_stripped.startswith(f"**{s}")
                                   for s in self.KNOWN_SECTIONS if s != section_name):
                                break
                            cleaned_lines.append(line)
                        cleaned_content = '\n'.join(cleaned_lines).strip()
                        if cleaned_content:
                            return cleaned_content
        return None

    def extract_list_section(self, text: str, section_names: List[str]) -> List[str]:
        """
        Extract list items from a section (bullet or numbered).
        Handles multi-line items and continuation lines.
        """
        section_text = self.extract_section(text, section_names)
        if not section_text:
            return []

        items = []
        list_item_patterns = [
            r"(?i)^\s*[0-9]+[\.\)]\s*(.+)$",
            r"(?i)^\s*[-*•]\s*(.+)$",
        ]
        continuation_pattern = r"^\s{2,}"

        def is_likely_new_action(line: str) -> bool:
            if not line or len(line.strip()) < 15:
                return False
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            action_starts = [
                'this involves', 'this requires', 'this includes', 'this means',
                'monitor', 'check', 'review', 'verify', 'ensure', 'implement',
                'set up', 'establish', 'develop', 'conduct', 'document',
                'regular', 'perform', 'analyze', 'investigate', 'inspect',
                'adjust', 'configure', 'update', 'maintain', 'schedule',
                'these', 'additionally', 'furthermore', 'also', 'next',
            ]
            for start in action_starts:
                if line_lower.startswith(start):
                    return True
            if line_stripped[0].isupper() and len(line_stripped.split()) >= 5:
                action_verbs = ['perform', 'adjust', 'review', 'monitor', 'check', 'verify',
                              'ensure', 'implement', 'establish', 'develop', 'conduct',
                              'document', 'analyze', 'investigate', 'inspect', 'configure',
                              'update', 'maintain', 'schedule', 'set']
                first_word = line_lower.split()[0] if line_lower.split() else ""
                if any(first_word.startswith(verb) for verb in action_verbs):
                    return True
                return True
            return False

        lines = section_text.split("\n")
        current_item = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                if current_item:
                    items.append(current_item)
                    current_item = None
                continue
            if line_stripped.startswith('#'):
                if current_item:
                    items.append(current_item)
                    current_item = None
                continue
            line_lower = line_stripped.lower()
            if (line_lower.startswith('immediate action') or line_lower.startswith('short-term action')
                    or line_lower.startswith('long-term action') or line_lower.startswith('action item')):
                if current_item:
                    items.append(current_item)
                    current_item = None
                continue

            is_list_item = False
            item_content = None
            for pattern in list_item_patterns:
                m = re.match(pattern, line_stripped)
                if m:
                    item_content = m.group(1).strip()
                    is_list_item = True
                    break

            if is_list_item:
                if current_item:
                    items.append(current_item)
                current_item = item_content if item_content and len(item_content) > 3 else None
            else:
                if current_item:
                    is_indented = bool(re.match(continuation_pattern, line))
                    is_new_action = is_likely_new_action(line_stripped)
                    prev_line_ended = False
                    if i > 0 and lines[i - 1].strip() and lines[i - 1].strip()[-1] in '.?:;':
                        prev_line_ended = True
                    strong_action_verbs = ['perform', 'adjust', 'implement', 'establish', 'develop',
                                           'conduct', 'execute', 'initiate', 'activate', 'configure']
                    starts_with_strong_verb = any(line_stripped.lower().startswith(v + ' ') for v in strong_action_verbs)
                    if is_indented and not is_new_action and not starts_with_strong_verb:
                        current_item += " " + line_stripped
                    elif is_new_action or starts_with_strong_verb or (prev_line_ended and len(line_stripped) > 20 and line_stripped[0].isupper()):
                        items.append(current_item)
                        current_item = line_stripped
                    elif line_stripped.startswith(('##', '**', '###')):
                        items.append(current_item)
                        current_item = None
                    else:
                        current_item += " " + line_stripped
                elif line_stripped and len(line_stripped) > 10:
                    if is_likely_new_action(line_stripped):
                        current_item = line_stripped
                    elif line_stripped[0].isupper() and len(line_stripped.split()) >= 5:
                        first_word_lower = line_stripped.split()[0].lower() if line_stripped.split() else ""
                        action_verbs = ['perform', 'adjust', 'review', 'monitor', 'check', 'verify',
                                      'ensure', 'implement', 'establish', 'develop', 'conduct',
                                      'document', 'analyze', 'investigate', 'inspect', 'configure',
                                      'update', 'maintain', 'schedule', 'set', 'create', 'execute']
                        if any(first_word_lower.startswith(verb) for verb in action_verbs):
                            current_item = line_stripped
                        else:
                            current_item = line_stripped

        if current_item:
            items.append(current_item)

        filtered = []
        for item in items:
            item = item.strip()
            if item and len(item) > 10:
                if item.endswith('?') and len(item.split()) < 5:
                    continue
                filtered.append(item)
        return filtered
