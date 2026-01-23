"""
Diagnostic Planner
Plans diagnostic tasks for site-level analysis
"""

import logging
from typing import Dict, Any, List, Optional

from ..llm_diagnostic.client import LLMClient
from .task_manager import DiagnosticTaskManager, DiagnosticTask

logger = logging.getLogger(__name__)


class DiagnosticPlanner:
    """Diagnostic task planner"""

    SYSTEM_PROMPT = """You are a BESS (Battery Energy Storage System) diagnostic planning expert.

Your role is to break down site diagnostic requests into a structured task list that can be executed by specialized diagnostic agents.

## Available Diagnostic Agents

1. **DataCollectorAgent**: Collects data from the system
   - Can collect: alarms, device status, historical time-series data
   - Task description should specify what data to collect (e.g., "Collect alarms for site X in time range Y")

2. **AlarmAnalyzerAgent**: Analyzes alarm patterns
   - Analyzes alarm types, severity distribution, time trends
   - Requires: alarm data from DataCollectorAgent
   - Task description should specify analysis focus (e.g., "Analyze alarm patterns, identify critical issues")

3. **DeviceAnalyzerAgent**: Analyzes device status
   - Analyzes device health, identifies abnormal devices
   - Requires: device data from DataCollectorAgent
   - Task description should specify analysis focus (e.g., "Analyze device status, identify unhealthy devices")

4. **TrendAnalyzerAgent**: Analyzes historical trends
   - Analyzes performance trends, identifies degradation
   - Requires: historical data from DataCollectorAgent
   - Task description should specify metrics to analyze (e.g., "Analyze SOC, SOH, temperature trends")

5. **CorrelationAgent**: Discovers correlations between different data sources
   - Finds relationships between alarms, devices, and trends
   - Requires: results from AlarmAnalyzerAgent, DeviceAnalyzerAgent, TrendAnalyzerAgent
   - Task description should specify what correlations to find

6. **ReportGeneratorAgent**: Generates final diagnostic report
   - Synthesizes all analysis results into a comprehensive report
   - Requires: results from CorrelationAgent
   - Task description should specify report format and focus

## Task Planning Guidelines

1. **Data Collection First**: Always start with data collection tasks (can be parallel)
2. **Analysis After Data**: Analysis tasks depend on data collection
3. **Correlation After Analysis**: Correlation depends on all analysis results
4. **Report Last**: Report generation depends on correlation results

## Example Task List

For a site diagnostic request:
- Task 1: Collect alarms (DataCollectorAgent, no dependencies)
- Task 2: Collect device data (DataCollectorAgent, no dependencies) [parallel with Task 1]
- Task 3: Collect historical data (DataCollectorAgent, no dependencies) [parallel with Task 1,2]
- Task 4: Analyze alarms (AlarmAnalyzerAgent, depends on Task 1)
- Task 5: Analyze devices (DeviceAnalyzerAgent, depends on Task 2)
- Task 6: Analyze trends (TrendAnalyzerAgent, depends on Task 3)
- Task 7: Find correlations (CorrelationAgent, depends on Task 4,5,6)
- Task 8: Generate report (ReportGeneratorAgent, depends on Task 7)

## Output Format

Return a JSON array of tasks, each with:
- task_id: string (e.g., "t1", "t2")
- agent: string (agent name)
- description: string (detailed task description)
- dependencies: array of task_ids (empty array if no dependencies)

Example:
[
  {
    "task_id": "t1",
    "agent": "DataCollectorAgent",
    "description": "Collect all alarms for site site_1 in time range -24h",
    "dependencies": []
  },
  {
    "task_id": "t2",
    "agent": "DataCollectorAgent",
    "description": "Collect device status data for site site_1",
    "dependencies": []
  }
]
"""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize diagnostic planner

        Args:
            llm_client: LLM client for planning
        """
        self.llm_client = llm_client
        logger.info("Diagnostic planner initialized")

    async def plan_diagnostic(
        self,
        site_id: str,
        time_range: str = "-24h",
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticTaskManager:
        """
        Plan diagnostic tasks for a site

        Args:
            site_id: Site ID to diagnose
            time_range: Time range for analysis (e.g., "-24h", "-7d")
            additional_context: Optional additional context

        Returns:
            DiagnosticTaskManager with planned tasks
        """
        # Build planning prompt
        prompt = self._build_planning_prompt(site_id, time_range, additional_context)

        try:
            # Call LLM to generate task list
            response = await self.llm_client.generate(prompt, self.SYSTEM_PROMPT)
            logger.info(f"Planner generated task list for site {site_id}")

            # Parse response to extract task list
            tasks = self._parse_task_list(response, site_id, time_range)

            # Create task manager
            task_manager = DiagnosticTaskManager()
            result = task_manager.create_tasks(tasks)

            if result.startswith("Error"):
                logger.error(f"Failed to create tasks: {result}")
                # Fallback to default task list
                tasks = self._create_default_tasks(site_id, time_range)
                task_manager = DiagnosticTaskManager()
                task_manager.create_tasks(tasks)

            logger.info(f"Created {len(task_manager.tasks)} tasks for site {site_id}")
            return task_manager

        except Exception as e:
            logger.error(f"Planning failed for site {site_id}: {e}", exc_info=True)
            # Fallback to default task list
            tasks = self._create_default_tasks(site_id, time_range)
            task_manager = DiagnosticTaskManager()
            task_manager.create_tasks(tasks)
            return task_manager

    def _build_planning_prompt(
        self,
        site_id: str,
        time_range: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build planning prompt"""
        prompt = f"""Plan diagnostic tasks for BESS Site {site_id}.

## Request Details
- Site ID: {site_id}
- Time Range: {time_range}
"""

        if additional_context:
            prompt += "\n## Additional Context\n"
            for key, value in additional_context.items():
                prompt += f"- {key}: {value}\n"

        prompt += """
## Task Planning Request
Create a comprehensive task list for diagnosing this site. The tasks should:
1. Collect all necessary data (alarms, devices, historical)
2. Analyze the collected data
3. Find correlations between different data sources
4. Generate a final diagnostic report

Return the task list as a JSON array.
"""

        return prompt

    def _parse_task_list(self, response: str, site_id: str, time_range: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract task list"""
        import json
        import re

        # Try to extract JSON from response
        # Look for JSON array in the response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            try:
                tasks = json.loads(json_match.group(0))
                # Validate tasks
                validated_tasks = []
                for task in tasks:
                    if isinstance(task, dict) and "task_id" in task and "agent" in task:
                        validated_tasks.append(task)
                if validated_tasks:
                    return validated_tasks
            except json.JSONDecodeError:
                pass

        # If parsing failed, return default tasks
        logger.warning("Failed to parse LLM response, using default tasks")
        return self._create_default_tasks(site_id, time_range)

    def _create_default_tasks(self, site_id: str, time_range: str) -> List[Dict[str, Any]]:
        """Create default task list"""
        return [
            {
                "task_id": "t1",
                "agent": "DataCollectorAgent",
                "description": f"Collect all alarms for site {site_id} in time range {time_range}",
                "dependencies": [],
            },
            {
                "task_id": "t2",
                "agent": "DataCollectorAgent",
                "description": f"Collect device status data for site {site_id}",
                "dependencies": [],
            },
            {
                "task_id": "t3",
                "agent": "DataCollectorAgent",
                "description": f"Collect historical time-series data for site {site_id} in time range {time_range} (metrics: soc, soh, temperature, voltage, current, power)",
                "dependencies": [],
            },
            {
                "task_id": "t4",
                "agent": "AlarmAnalyzerAgent",
                "description": f"Analyze alarm patterns for site {site_id}, identify alarm types, severity distribution, and time trends",
                "dependencies": ["t1"],
            },
            {
                "task_id": "t5",
                "agent": "DeviceAnalyzerAgent",
                "description": f"Analyze device status for site {site_id}, identify unhealthy devices and device health issues",
                "dependencies": ["t2"],
            },
            {
                "task_id": "t6",
                "agent": "TrendAnalyzerAgent",
                "description": f"Analyze historical trends for site {site_id}, identify performance degradation and anomalies",
                "dependencies": ["t3"],
            },
            {
                "task_id": "t7",
                "agent": "CorrelationAgent",
                "description": f"Find correlations between alarms, devices, and trends for site {site_id}, identify root causes",
                "dependencies": ["t4", "t5", "t6"],
            },
            {
                "task_id": "t8",
                "agent": "ReportGeneratorAgent",
                "description": f"Generate comprehensive diagnostic report for site {site_id}, including current status, risk level, root causes, and recommended actions",
                "dependencies": ["t7"],
            },
        ]

