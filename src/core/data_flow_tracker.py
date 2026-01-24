"""
Data Flow Tracker
Tracks data flow through the system for monitoring and observability
"""

import logging
from datetime import UTC, datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class DataFlowTrace:
    """Data flow trace entry"""
    data_id: str
    stage: str
    timestamp: datetime
    metadata: Dict[str, Any]
    duration_ms: Optional[float] = None
    status: str = "success"  # success, error, duplicate, skipped


class DataFlowTracker:
    """
    Tracks data flow through the system
    Records traces for monitoring and observability
    """

    def __init__(self, max_traces: int = 1000, enable_logging: bool = True):
        """
        Initialize data flow tracker

        Args:
            max_traces: Maximum number of traces to keep in memory
            enable_logging: If True, log traces to logger
        """
        self.max_traces = max_traces
        self.enable_logging = enable_logging
        self._traces: List[DataFlowTrace] = []
        self._stage_timestamps: Dict[str, Dict[str, datetime]] = {}  # data_id -> stage -> timestamp

    def track(
        self,
        stage: str,
        data_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> None:
        """
        Track a data flow stage

        Args:
            stage: Stage name (e.g., "input", "rule_evaluation", "llm_diagnostic")
            data_id: Unique identifier for the data (e.g., device_id)
            metadata: Optional metadata dictionary
            status: Status of the stage (success, error, duplicate, skipped)
        """
        timestamp = datetime.now(UTC)
        metadata = metadata or {}

        # Calculate duration if previous stage exists
        duration_ms = None
        if data_id in self._stage_timestamps:
            previous_stages = self._stage_timestamps[data_id]
            if previous_stages:
                last_stage = max(previous_stages.items(), key=lambda x: x[1])
                duration_ms = (timestamp - last_stage[1]).total_seconds() * 1000

        # Record timestamp for this stage
        if data_id not in self._stage_timestamps:
            self._stage_timestamps[data_id] = {}
        self._stage_timestamps[data_id][stage] = timestamp

        # Create trace
        trace = DataFlowTrace(
            data_id=data_id,
            stage=stage,
            timestamp=timestamp,
            metadata=metadata,
            duration_ms=duration_ms,
            status=status,
        )

        # Add to traces (with size limit)
        self._traces.append(trace)
        if len(self._traces) > self.max_traces:
            # Remove oldest traces
            removed = self._traces.pop(0)
            # Clean up timestamps for removed trace if it's the last one for that data_id
            if removed.data_id in self._stage_timestamps:
                if removed.stage in self._stage_timestamps[removed.data_id]:
                    del self._stage_timestamps[removed.data_id][removed.stage]
                if not self._stage_timestamps[removed.data_id]:
                    del self._stage_timestamps[removed.data_id]

        # Log trace if enabled
        if self.enable_logging:
            duration_str = f", duration={duration_ms:.2f}ms" if duration_ms else ""
            log_msg = (
                f"📊 [FlowTrace] {stage}: data_id={data_id}, status={status}{duration_str}"
            )
            if metadata:
                log_msg += f", metadata={metadata}"
            
            if status == "error":
                logger.error(log_msg)
            elif status in ["duplicate", "skipped"]:
                logger.debug(log_msg)
            else:
                logger.debug(log_msg)

    def get_traces_for_data(self, data_id: str) -> List[DataFlowTrace]:
        """
        Get all traces for a specific data ID

        Args:
            data_id: Data ID to get traces for

        Returns:
            List of traces for the data ID
        """
        return [trace for trace in self._traces if trace.data_id == data_id]

    def get_recent_traces(self, limit: int = 100) -> List[DataFlowTrace]:
        """
        Get recent traces

        Args:
            limit: Maximum number of traces to return

        Returns:
            List of recent traces
        """
        return self._traces[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about data flow

        Returns:
            Dictionary with statistics
        """
        if not self._traces:
            return {
                "total_traces": 0,
                "stages": {},
                "status_counts": {},
            }

        # Count by stage
        stage_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        stage_durations: Dict[str, List[float]] = {}

        for trace in self._traces:
            # Count stages
            stage_counts[trace.stage] = stage_counts.get(trace.stage, 0) + 1
            
            # Count statuses
            status_counts[trace.status] = status_counts.get(trace.status, 0) + 1
            
            # Collect durations
            if trace.duration_ms is not None:
                if trace.stage not in stage_durations:
                    stage_durations[trace.stage] = []
                stage_durations[trace.stage].append(trace.duration_ms)

        # Calculate average durations
        avg_durations = {}
        for stage, durations in stage_durations.items():
            if durations:
                avg_durations[stage] = sum(durations) / len(durations)

        return {
            "total_traces": len(self._traces),
            "stages": stage_counts,
            "status_counts": status_counts,
            "average_durations_ms": avg_durations,
        }

    def clear(self):
        """Clear all traces"""
        self._traces.clear()
        self._stage_timestamps.clear()
        logger.debug("Data flow traces cleared")














