"""
Report Formatter Agent
Specialized agent for cleaning and formatting diagnostic reports
Removes all Markdown symbols and ensures clean plain text output
"""

import re
import logging
from typing import Dict, Any, Optional, List

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class FormatterAgent(BaseDiagnosticAgent):
    """Agent for cleaning and formatting diagnostic reports"""

    SYSTEM_PROMPT = """You are a text formatting expert specialized in cleaning diagnostic reports.

Your ONLY job is to remove ALL Markdown formatting symbols from text while preserving the content.

Rules:
1. Remove ALL ** (double asterisks) and * (single asterisks) symbols
2. Remove ALL backticks `
3. Remove ALL markdown links [text](url) - keep only the text
4. Convert numbered lists (1., 2., 3.) to bullet points (-)
5. Keep only ## for headers (convert ### and #### to ##)
6. Remove section labels like "Immediate Actions:", "Short-Term Actions:" etc.
7. Remove "Action Item", "Prioritized Action Items" prefixes
8. Remove patterns like "(Highest Priority):" or "(Priority):"
9. Keep the content but remove ALL formatting symbols
10. Output clean, plain text only

Return the cleaned text without any explanation or additional text.
"""

    def __init__(self, llm_client: LLMClient):
        """Initialize formatter agent"""
        super().__init__(self.SYSTEM_PROMPT, llm_client, "FormatterAgent")

    async def format_text(self, text: str) -> str:
        """
        Clean and format text by removing all Markdown symbols
        
        Args:
            text: Raw text with potential Markdown formatting
            
        Returns:
            Cleaned plain text without any Markdown symbols
        """
        if not text:
            return text
        
        # Step 1: Aggressive removal of all markdown symbols
        cleaned = self._remove_all_markdown_symbols(text)
        
        # Step 2: Clean up structure (lists, headers, etc.)
        cleaned = self._clean_structure(cleaned)
        
        # Step 3: Remove unwanted patterns and labels
        cleaned = self._remove_unwanted_patterns(cleaned)
        
        # Step 4: Final pass - ensure no symbols remain
        cleaned = self._final_cleanup(cleaned)
        
        logger.debug(f"[FormatterAgent] Cleaned text length: {len(text)} -> {len(cleaned)}")
        
        return cleaned

    def _remove_all_markdown_symbols(self, text: str) -> str:
        """Remove all markdown symbols aggressively"""
        # Remove all ** and * (very aggressive - 50 passes)
        for _ in range(50):
            text = text.replace('**', '')
            text = text.replace('*', '')
        
        # Remove backticks
        for _ in range(20):
            text = text.replace('`', '')
        
        # Remove markdown links [text](url) - keep only text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove markdown images ![alt](url)
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
        
        # Remove markdown code blocks ```code```
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`[^`]*`', '', text)
        
        return text

    def _clean_structure(self, text: str) -> str:
        """Clean up document structure"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            # Skip empty lines at start
            if not line and not cleaned_lines:
                continue
            
            # Remove any remaining markdown symbols from line
            for _ in range(10):
                line = line.replace('**', '')
                line = line.replace('*', '')
                line = line.replace('`', '')
            
            # Clean headers - convert ### and #### to ##
            if line.startswith('#'):
                # Convert ### and #### to ##
                if line.startswith('###') or line.startswith('####'):
                    line = re.sub(r'^#+', '##', line)
                # Remove any remaining symbols
                for _ in range(5):
                    line = line.replace('**', '')
                    line = line.replace('*', '')
                cleaned_lines.append(line)
                continue
            
            # Convert numbered lists to bullet points
            numbered_match = re.match(r'^\s*(\d+)[\.\)]\s*(.+)$', line)
            if numbered_match:
                content = numbered_match.group(2).strip()
                # Remove all symbols
                for _ in range(10):
                    content = content.replace('**', '')
                    content = content.replace('*', '')
                    content = content.replace('`', '')
                # Clean up
                content = re.sub(r'\s+', ' ', content).strip()
                if content and len(content) > 3:
                    cleaned_lines.append(f"- {content}")
                continue
            
            # Process bullet points
            bullet_match = re.match(r'^\s*[-*•]\s*(.+)$', line)
            if bullet_match:
                content = bullet_match.group(1).strip()
                # Remove all symbols
                for _ in range(10):
                    content = content.replace('**', '')
                    content = content.replace('*', '')
                    content = content.replace('`', '')
                # Clean up
                content = re.sub(r'\s+', ' ', content).strip()
                if content and len(content) > 3:
                    cleaned_lines.append(f"- {content}")
                continue
            
            # Regular text - remove symbols and clean
            if line:
                for _ in range(10):
                    line = line.replace('**', '')
                    line = line.replace('*', '')
                    line = line.replace('`', '')
                line = re.sub(r'\s+', ' ', line).strip()
                if line:
                    cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def _remove_unwanted_patterns(self, text: str) -> str:
        """Remove unwanted patterns and labels"""
        lines = text.split('\n')
        cleaned_lines = []
        skip_next = False
        
        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue
            
            line_lower = line.lower().strip()
            
            # Skip section labels
            if (line_lower.startswith('immediate action') or
                line_lower.startswith('short-term action') or
                line_lower.startswith('long-term action') or
                line_lower.startswith('preventive measure') or
                line_lower.startswith('action item') or
                'immediate actions' in line_lower or
                'short-term actions' in line_lower or
                'long-term actions' in line_lower or
                line_lower == 'action:' or
                line_lower == 'reasoning:' or
                line_lower.startswith('reasoning:')):
                # Check if next line should be merged
                if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].strip().startswith('-'):
                    skip_next = True
                continue
            
            # Remove patterns like "(Highest Priority):" or "(Priority):"
            line = re.sub(r'\s*\([^\)]*priority[^\)]*\):\s*', ': ', line, flags=re.IGNORECASE)
            
            # Remove "Action Item" prefixes
            line = re.sub(r'^(Action\s+Item\s*\d*[:\-]?\s*)', '', line, flags=re.IGNORECASE)
            
            # Remove "Prioritized Action Items" prefixes
            line = re.sub(r'^(Prioritized\s+Action\s+Items\s+for\s+.+?:\s*)', '', line, flags=re.IGNORECASE)
            
            # Remove colons at end if it's just a title
            if line.endswith(':') and not line.startswith('##'):
                # Check if next line is continuation
                if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].strip().startswith('-'):
                    next_line = lines[i + 1].strip()
                    line = line.rstrip(':') + ' ' + next_line
                    skip_next = True
            
            if line.strip():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def _final_cleanup(self, text: str) -> str:
        """Final cleanup pass - ensure no symbols remain"""
        # Remove all markdown symbols one more time (100 passes to be absolutely sure)
        for _ in range(100):
            text = text.replace('**', '')
            text = text.replace('*', '')
            text = text.replace('`', '')
        
        # Remove patterns like "**text**:" even if somehow they remain
        text = re.sub(r'\*\*([^*]+)\*\*:\s*', r'\1: ', text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text, flags=re.MULTILINE)
        
        # Remove any remaining asterisks
        text = re.sub(r'\*+', '', text)
        
        # Clean up multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Clean up multiple empty lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove empty lines between list items
        text = re.sub(r'(-\s+.+)\n\n(-)', r'\1\n\2', text)
        
        return text.strip()

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Format text from context
        
        Args:
            context: Must contain 'text' key with text to format
            dependencies: Not used
            
        Returns:
            Formatted result with cleaned text
        """
        text = context.get('text', '')
        if not text:
            return {
                "status": "error",
                "message": "No text provided in context",
            }
        
        try:
            cleaned_text = await self.format_text(text)
            
            return {
                "status": "success",
                "agent": self.agent_name,
                "cleaned_text": cleaned_text,
                "original_length": len(text),
                "cleaned_length": len(cleaned_text),
            }
        except Exception as e:
            logger.error(f"[FormatterAgent] Error formatting text: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error formatting text: {str(e)}",
            }

    async def process(self, prompt: str) -> str:
        """
        Process a prompt and return cleaned text
        
        Args:
            prompt: Text to format/clean
            
        Returns:
            Cleaned text
        """
        return await self.format_text(prompt)

