"""
Command registry and execution
"""

from typing import Callable, Dict, Tuple

from .collect import collect_data
from .grafana import check_grafana, create_grafana_key, fix_grafana, setup_grafana
from .influxdb import check_influxdb
from .service import get_port, start_agent, stop_agent
from .status import check_emqx, check_status
from .test import test_agent
from .utils import show_pids

# Command registry: command_name -> (function, description)
COMMANDS: Dict[str, Tuple[Callable, str]] = {
    "start": (start_agent, "Start Agent service"),
    "stop": (stop_agent, "Stop Agent service"),
    "status": (check_status, "Check system health status"),
    "health": (check_status, "Check system health status (alias)"),
    "ps": (show_pids, "Show all service PIDs"),
    "pids": (show_pids, "Show all service PIDs (alias)"),
    "list": (show_pids, "Show all service PIDs (alias)"),
    "get-port": (get_port, "Get current agent service port"),
    "port": (get_port, "Get current agent service port (alias)"),
    "create-grafana-key": (create_grafana_key, "Create Grafana API Key"),
    "setup-grafana": (setup_grafana, "Setup Grafana (data source and dashboard)"),
    "check-grafana": (check_grafana, "Check Grafana configuration"),
    "fix-grafana": (fix_grafana, "Fix Grafana datasource references"),
    "check-influxdb": (check_influxdb, "Check InfluxDB data"),
    "check-emqx": (check_emqx, "Check EMQX (MQTT Broker) status"),
    "check-mqtt": (check_emqx, "Check MQTT/EMQX status (alias)"),
    "collect": (collect_data, "Run data collection"),
    "test": (test_agent, "Run Agent test suite"),
}


def get_command(command_name: str) -> Tuple[Callable, str]:
    """Get command function and description"""
    return COMMANDS.get(command_name, (None, ""))


def list_commands() -> Dict[str, str]:
    """List all available commands"""
    return {name: desc for name, (_, desc) in COMMANDS.items()}
