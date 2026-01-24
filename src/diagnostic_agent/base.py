"""
Base Diagnostic Agent
Abstract base class for all diagnostic agents
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ..llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class BaseDiagnosticAgent(ABC):
    """Base class for all diagnostic agents"""

    def __init__(
        self,
        system_prompt: str,
        llm_client: LLMClient,
        agent_name: Optional[str] = None,
    ):
        """
        Initialize base diagnostic agent

        Args:
            system_prompt: System prompt for this agent
            llm_client: LLM client instance
            agent_name: Agent name (default: class name)
        """
        self.system_prompt = system_prompt
        self.llm_client = llm_client
        self.agent_name = agent_name or self.__class__.__name__
        logger.debug(f"Initialized {self.agent_name}")

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute analysis task

        Args:
            context: Task context (site_id, time_range, task_description, etc.)
            dependencies: List of dependency task results

        Returns:
            Analysis result dictionary
        """
        try:
            # Build prompt with context and dependencies
            prompt = self._build_prompt(context, dependencies)

            # Call LLM
            result_text = await self.llm_client.generate(
                prompt, system_prompt=self.system_prompt
            )

            # Parse result
            result = self._parse_result(result_text, context)

            logger.info(
                f"{self.agent_name} completed analysis for site {context.get('site_id', 'unknown')}"
            )
            return result

        except Exception as e:
            logger.error(f"{self.agent_name} analysis failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "agent": self.agent_name,
            }

    def _build_prompt(
        self, context: Dict[str, Any], dependencies: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Build prompt for agent, including dependency results as context

        Args:
            context: Task context
            dependencies: List of dependency task results

        Returns:
            Complete prompt string
        """
        prompt_parts = []

        # Add dependency results if available
        if dependencies:
            prompt_parts.append("## Previous Task Results\n")
            for dep in dependencies:
                task_id = dep.get("task_id", "unknown")
                description = dep.get("description", "")
                result = dep.get("result", {})
                error = dep.get("error")

                prompt_parts.append(f"### Task {task_id}: {description}")
                if error:
                    prompt_parts.append(f"Failed:\n```\n{error}\n```\n")
                elif result:
                    # Format result nicely
                    if isinstance(result, dict):
                        result_str = self._format_dict_result(result)
                    else:
                        result_str = str(result)
                    prompt_parts.append(f"Result:\n```\n{result_str}\n```\n")

        # Add current task context
        prompt_parts.append("## Current Task\n")
        task_description = context.get("task_description", "")
        if task_description:
            prompt_parts.append(task_description)
        else:
            prompt_parts.append(f"Analyze site {context.get('site_id', 'unknown')}")

        # Add additional context
        site_id = context.get("site_id")
        time_range = context.get("time_range", "-24h")
        if site_id:
            prompt_parts.append(f"\nSite ID: {site_id}")
        if time_range:
            prompt_parts.append(f"Time Range: {time_range}")

        return "\n".join(prompt_parts)

    def _format_dict_result(self, result: Dict[str, Any], indent: int = 0) -> str:
        """Format dictionary result for prompt"""
        lines = []
        prefix = "  " * indent
        for key, value in result.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_dict_result(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: [{len(value)} items]")
                if len(value) > 0 and isinstance(value[0], dict):
                    # Show first item as example
                    lines.append(f"{prefix}  Example:")
                    lines.append(self._format_dict_result(value[0], indent + 2))
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)

    def _parse_result(self, result_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse LLM result into structured format

        Args:
            result_text: Raw LLM response
            context: Original context

        Returns:
            Parsed result dictionary
        """
        # Default implementation: return text as analysis
        # Subclasses can override for more structured parsing
        return {
            "status": "success",
            "agent": self.agent_name,
            "analysis": result_text,
            "site_id": context.get("site_id"),
        }

    @abstractmethod
    async def process(self, prompt: str) -> str:
        """
        Process a prompt and return response (used by executor)

        Args:
            prompt: Task prompt/description

        Returns:
            Agent response as string
        """
        pass








