#!/usr/bin/env python3
"""
BESS Agent Unified CLI Tool
All-in-one command-line interface for Agent management
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import CLI modules (after path setup)
from scripts.cli.collect import collect_data  # noqa: E402
from scripts.cli.grafana import (  # noqa: E402
    check_grafana,
    create_grafana_key,
    fix_grafana,
    setup_grafana,
)
from scripts.cli.influxdb import check_influxdb  # noqa: E402
from scripts.cli.interactive import interactive_mode  # noqa: E402
from scripts.cli.service import get_port, start_agent, stop_agent  # noqa: E402
from scripts.cli.status import check_emqx, check_status  # noqa: E402
from scripts.cli.test import test_agent  # noqa: E402
from scripts.cli.utils import show_pids  # noqa: E402


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="BESS Agent Unified CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start              # Start Agent service
  %(prog)s stop               # Stop Agent service
  %(prog)s status             # Check system health
  %(prog)s setup-grafana      # Setup Grafana
  %(prog)s create-grafana-key # Create Grafana API Key
  %(prog)s test               # Run test suite
  %(prog)s collect            # Run data collection
  %(prog)s                    # Enter interactive mode
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Service management
    start_parser = subparsers.add_parser("start", help="Start Agent service")
    start_parser.add_argument(
        "--port", type=int, help="Port number (default: auto-detect)"
    )
    start_parser.add_argument(
        "--background", "-b", action="store_true", help="Start service in background"
    )

    subparsers.add_parser("stop", help="Stop Agent service")
    subparsers.add_parser("status", help="Check system health status")
    subparsers.add_parser("health", help="Check system health (alias for status)")
    subparsers.add_parser("ps", help="Show all service PIDs")
    subparsers.add_parser("pids", help="Show all service PIDs (alias)")
    subparsers.add_parser("list", help="Show all service PIDs (alias)")
    subparsers.add_parser("get-port", help="Get current agent service port")
    subparsers.add_parser("port", help="Get current agent service port (alias)")

    # Grafana
    subparsers.add_parser("create-grafana-key", help="Create Grafana API Key")
    subparsers.add_parser(
        "setup-grafana", help="Setup Grafana (data source and dashboard)"
    )
    subparsers.add_parser("check-grafana", help="Check Grafana configuration")
    subparsers.add_parser("fix-grafana", help="Fix Grafana datasource references")

    # Data
    subparsers.add_parser("check-influxdb", help="Check InfluxDB data")
    subparsers.add_parser("check-emqx", help="Check EMQX (MQTT Broker) status")
    subparsers.add_parser("check-mqtt", help="Check MQTT/EMQX status (alias)")
    subparsers.add_parser("collect", help="Run data collection")

    # Testing
    subparsers.add_parser("test", help="Run Agent test suite")

    # Interactive mode
    subparsers.add_parser("interactive", help="Enter interactive mode")
    subparsers.add_parser("i", help="Enter interactive mode (shortcut)")

    args = parser.parse_args()

    # If no command provided, enter interactive mode
    if not args.command:
        interactive_mode()
        return 0

    # Execute command
    if args.command == "start":
        return 0 if start_agent(args.port, background=args.background) else 1
    elif args.command == "stop":
        return 0 if stop_agent() else 1
    elif args.command in ["status", "health"]:
        check_status()
        return 0
    elif args.command in ["ps", "pids", "list"]:
        show_pids()
        return 0
    elif args.command in ["get-port", "port"]:
        return 0 if get_port() else 1
    elif args.command == "create-grafana-key":
        return 0 if create_grafana_key() else 1
    elif args.command == "setup-grafana":
        return 0 if setup_grafana() else 1
    elif args.command == "check-grafana":
        return 0 if check_grafana() else 1
    elif args.command == "fix-grafana":
        return 0 if fix_grafana() else 1
    elif args.command == "check-influxdb":
        return 0 if check_influxdb() else 1
    elif args.command in ["check-emqx", "check-mqtt"]:
        return 0 if check_emqx() else 1
    elif args.command == "collect":
        return 0 if collect_data() else 1
    elif args.command == "test":
        return 0 if test_agent() else 1
    elif args.command in ["interactive", "i"]:
        interactive_mode()
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
