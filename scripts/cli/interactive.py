"""
Interactive CLI mode
"""

import shlex
from pathlib import Path

try:
    import readline

    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

from .commands import COMMANDS, get_command

PROJECT_ROOT = Path(__file__).parent.parent.parent


def print_help():
    """Print help message"""
    print("\n" + "=" * 60)
    print("BESS Agent CLI - Available Commands")
    print("=" * 60)
    print("\nService Management:")
    print("  start              - Start Agent service (background in interactive mode)")
    print("  stop               - Stop Agent service")
    print("  status             - Check system health status")
    print("  health             - Check system health (alias for status)")
    print("  ps, pids, list     - Show all service PIDs")
    print("  get-port, port     - Get current agent service port")
    print("\nGrafana Management:")
    print("  create-grafana-key - Create Grafana API Key")
    print("  setup-grafana      - Setup Grafana (data source and dashboard)")
    print("  check-grafana      - Check Grafana configuration")
    print("  fix-grafana        - Fix Grafana datasource references")
    print("\nData Management:")
    print("  check-influxdb     - Check InfluxDB data")
    print("  check-emqx         - Check EMQX (MQTT Broker) status")
    print("  check-mqtt         - Check MQTT/EMQX status (alias)")
    print("  collect            - Run data collection")
    print("\nTesting:")
    print("  test               - Run Agent test suite")
    print("\nOther:")
    print("  help               - Show this help message")
    print("  exit, quit         - Exit interactive mode")
    print("=" * 60 + "\n")


def setup_readline():
    """Setup readline for better interactive experience"""
    if not READLINE_AVAILABLE:
        return

    # Command completion
    def completer(text, state):
        options = [cmd for cmd in COMMANDS.keys() if cmd.startswith(text)]
        options.extend(["help", "exit", "quit"])
        if state < len(options):
            return options[state]
        return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    # History file
    history_file = PROJECT_ROOT / ".agent_cli_history"
    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass

    # Save history on exit
    import atexit

    atexit.register(readline.write_history_file, str(history_file))


def interactive_mode():
    """Interactive CLI mode"""
    print("\n" + "=" * 60)
    print("BESS Agent Interactive CLI")
    print("=" * 60)
    print("Type 'help' for available commands, 'exit' or 'quit' to exit")
    print("=" * 60 + "\n")

    setup_readline()

    while True:
        try:
            try:
                command = input("agent> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nExiting...")
                break

            if not command:
                continue

            # Parse command
            parts = shlex.split(command)
            if not parts:
                continue

            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            # Handle special commands
            if cmd in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            elif cmd in ["help", "h", "?"]:
                print_help()
                continue

            # Execute command
            func, _ = get_command(cmd)
            if func:
                try:
                    # Handle commands with arguments
                    if cmd == "start":
                        # In interactive mode, always start in background
                        if args:
                            try:
                                port = int(args[0])
                                func(port, background=True)
                            except ValueError:
                                print(f"✗ Error: Invalid port number: {args[0]}")
                        else:
                            func(background=True)
                    else:
                        func()
                except KeyboardInterrupt:
                    print("\n\nCommand interrupted")
                except Exception as e:
                    print(f"✗ Error executing command: {e}")
            else:
                print(f"✗ Unknown command: {cmd}")
                print("Type 'help' for available commands")

        except Exception as e:
            print(f"✗ Error: {e}")
