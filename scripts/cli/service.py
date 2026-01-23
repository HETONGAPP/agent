"""
Service management commands
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_port(port):
    """Check if port is occupied"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(0.1)
            result = s.connect_ex(("localhost", port))
            return result == 0
        except Exception:
            return False


def find_available_port(start_port=8000, max_attempts=10):
    """Find available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        if not check_port(port):
            return port
    return None


def save_port_to_file(port):
    """Save port number to file for other programs to read"""
    port_file = PROJECT_ROOT / "logs" / "agent_port.txt"
    try:
        port_file.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        with open(port_file, "w") as f:
            f.write(str(port))
        port_file.chmod(0o644)
        return port_file
    except (PermissionError, OSError) as e:
        print(f"⚠ Warning: Could not save port to file: {e}")
        return None


def get_current_port():
    """Get current agent service port from file or process"""
    port_file = PROJECT_ROOT / "logs" / "agent_port.txt"
    if port_file.exists():
        try:
            with open(port_file, "r") as f:
                port = int(f.read().strip())
                if check_port(port):
                    return port
        except (ValueError, FileNotFoundError):
            pass

    # Try to find from running processes
    try:
        result = subprocess.run(
            ["ps", "aux"] if sys.platform != "win32" else ["tasklist"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.split("\n"):
            if "uvicorn" in line and "main:app" in line:
                parts = line.split()
                try:
                    if "--port" in parts:
                        port_idx = parts.index("--port")
                        if port_idx + 1 < len(parts):
                            return int(parts[port_idx + 1])
                except (ValueError, IndexError):
                    continue
    except Exception:
        pass

    return None


def find_agent_processes():
    """Find all Agent service processes"""
    pids = []

    try:
        result = subprocess.run(
            ["ps", "aux"] if sys.platform != "win32" else ["tasklist"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return pids

        for line in result.stdout.split("\n"):
            if not line.strip():
                continue

            if line.strip().startswith("USER") or "PID" in line[:10]:
                continue

            line_lower = line.lower()
            has_uvicorn = "uvicorn" in line_lower
            has_agent_main = (
                "main:app" in line
                or "src.agent.main" in line
                or "agent.main" in line
                or "agent/main" in line
            )

            if has_uvicorn and has_agent_main:
                parts = line.split()
                if parts and len(parts) > 1:
                    try:
                        pid = int(
                            parts[1]
                            if sys.platform != "win32"
                            else parts[1].split(".")[0]
                        )
                        current_pid = os.getpid()
                        if pid != current_pid and pid not in pids:
                            pids.append(pid)
                    except (ValueError, IndexError):
                        continue
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    return pids


def remove_port_file():
    """Remove port file when service stops"""
    port_file = PROJECT_ROOT / "logs" / "agent_port.txt"
    if port_file.exists():
        try:
            port_file.unlink()
        except Exception:
            pass


def start_agent(port=None, background=False):
    """Start Agent service"""
    print_header("Starting BESS Agent Service")

    # Check for virtual environment - prefer activated venv, fallback to project venv
    venv_python = None
    venv_path = None
    
    # First, check if VIRTUAL_ENV is set (activated virtual environment)
    if os.environ.get("VIRTUAL_ENV"):
        venv_path = Path(os.environ["VIRTUAL_ENV"])
        venv_python = venv_path / "bin" / "python"
        if not venv_python.exists():
            venv_python = venv_path / "Scripts" / "python.exe"
        if venv_python.exists():
            print(f"✓ Using activated virtual environment: {venv_path}")
    
    # Fallback to project venv if activated venv not found
    if not venv_python or not venv_python.exists():
        venv_path = PROJECT_ROOT / "venv"
        venv_python = venv_path / "bin" / "python"
        if not venv_python.exists():
            venv_python = venv_path / "Scripts" / "python.exe"
        if venv_python.exists():
            print(f"✓ Using project virtual environment: {venv_path}")
    
    # If still no venv found, try using current Python interpreter
    if not venv_python or not venv_python.exists():
        current_python = sys.executable
        if current_python and Path(current_python).exists():
            print(f"⚠ Warning: No virtual environment found, using current Python: {current_python}")
            venv_python = Path(current_python)
        else:
            print("✗ Error: Virtual environment does not exist")
            print(
                "Please run one of:\n"
                "  - python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt\n"
                "  - Or activate an existing virtual environment: source <venv_path>/bin/activate"
            )
            return False

    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print("⚠ Warning: .env file does not exist, using default configuration")

    # Determine port
    if port is None:
        preferred_port = 8000
        if check_port(preferred_port):
            print(
                f"⚠ Warning: Port {preferred_port} is occupied, finding alternative port..."
            )
            port = find_available_port(preferred_port + 1, max_attempts=20)
            if port is None:
                print(
                    f"✗ Error: Could not find an available port (tried {preferred_port + 1}-{preferred_port + 20})"
                )
                return False
            print(f"✓ Using alternative port: {port}")
        else:
            port = preferred_port
            print(f"✓ Using default port: {port}")
    else:
        if check_port(port):
            print(f"✗ Error: Port {port} is already in use")
            return False
        print(f"✓ Using specified port: {port}")

    port_file = save_port_to_file(port)
    if port_file:
        print(f"Port saved to: {port_file}")

    print(f"Project directory: {PROJECT_ROOT}")
    print(f"API documentation: http://localhost:{port}/docs")

    try:
        os.chdir(PROJECT_ROOT)
        cmd = [
            str(venv_python),
            "-m",
            "uvicorn",
            "src.agent.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--reload",
            "--log-level",
            "info",  # Set to INFO to see detailed MQTT logs
            "--use-colors",  # Enable colored logging output
            "--access-log",  # Enable access log (we'll filter WebSocket messages in code)
        ]

        if background:
            log_file = PROJECT_ROOT / "logs" / "agent_service.log"
            pid_file = PROJECT_ROOT / "logs" / "agent_service.pid"

            try:
                log_file.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            except (PermissionError, OSError) as e:
                print(f"⚠ Warning: Could not create logs directory: {e}")
                log_file = None

            try:
                if log_file:
                    with open(log_file, "a") as f:
                        process = subprocess.Popen(
                            cmd,
                            stdout=f,
                            stderr=subprocess.STDOUT,
                            cwd=str(PROJECT_ROOT),
                            start_new_session=True,
                        )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        cwd=str(PROJECT_ROOT),
                        start_new_session=True,
                    )
            except Exception as e:
                print(f"✗ Error starting service: {e}")
                return False

            try:
                with open(pid_file, "w") as f:
                    f.write(str(process.pid))
                pid_saved = True
            except (PermissionError, OSError) as e:
                print(f"⚠ Warning: Could not save PID to file: {e}")
                pid_saved = False

            print(f"✓ Service started in background (PID: {process.pid})")
            print(f"  Port: {port}")
            if port_file:
                print(f"  Port file: {port_file}")
            print(f"  Log file: {log_file}")
            if not pid_saved:
                print("  ⚠ PID file not saved (permission issue)")
            print("  Use 'stop' command to stop the service")
            return True
        else:
            print("Press Ctrl+C to stop service\n")
            subprocess.run(cmd)
            return True
    except KeyboardInterrupt:
        print("\n✓ Service stopped")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def stop_agent():
    """Stop Agent service"""
    print_header("Stopping BESS Agent Service")

    pids = []

    pid_file = PROJECT_ROOT / "logs" / "agent_service.pid"
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
                pids.append(pid)
        except (ValueError, FileNotFoundError):
            pass

    found_pids = find_agent_processes()
    for pid in found_pids:
        if pid not in pids:
            pids.append(pid)

    if not pids:
        print("✓ No running Agent services found")
        if pid_file.exists():
            pid_file.unlink()
        remove_port_file()
        return True

    print(f"Found {len(pids)} running service(s)")
    stopped_count = 0
    for pid in pids:
        try:
            os.kill(pid, 0)

            try:
                proc_result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "args="],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                cmd_line = (
                    proc_result.stdout.strip() if proc_result.returncode == 0 else "N/A"
                )
                port_info = ""
                if "--port" in cmd_line:
                    parts = cmd_line.split()
                    try:
                        port_idx = parts.index("--port")
                        if port_idx + 1 < len(parts):
                            port = parts[port_idx + 1]
                            port_info = f" (port {port})"
                    except (ValueError, IndexError):
                        pass
            except Exception:
                port_info = ""

            os.kill(pid, signal.SIGTERM)
            print(f"✓ Stopped process {pid}{port_info}")
            stopped_count += 1

            time.sleep(0.5)

            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
                print(f"  → Force killed process {pid}")
                time.sleep(0.2)
            except ProcessLookupError:
                pass
            except OSError:
                pass

        except ProcessLookupError:
            print(f"⚠ Process {pid} already stopped")
        except PermissionError:
            print(f"⚠ Need root permission to stop process {pid}")
            print(f"  Please run: sudo kill {pid}")
        except OSError as e:
            print(f"⚠ Process {pid} not found: {e}")

    if stopped_count > 0:
        print(f"\n✓ Successfully stopped {stopped_count} service(s)")

    if pid_file.exists():
        try:
            pid_file.unlink()
        except Exception:
            pass

    remove_port_file()

    print("\nVerifying services are stopped...")
    time.sleep(1)
    remaining = find_agent_processes()
    if remaining:
        print(f"⚠ Warning: {len(remaining)} service(s) still running: {remaining}")
    else:
        print("✓ All Agent services stopped")

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
        )
        if "bess-agent" in result.stdout:
            subprocess.run(["docker", "stop", "bess-agent"], check=False)
            print("✓ Stopped Docker container: bess-agent")
    except Exception:
        pass

    return True


def get_port():
    """Get current agent service port"""
    print_header("Agent Service Port")

    port = get_current_port()
    if port:
        print(f"Current port: {port}")
        print(f"API URL: http://localhost:{port}")
        print(f"API docs: http://localhost:{port}/docs")

        try:
            import requests

            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                print("✓ Service is running and healthy")
            else:
                print(f"⚠ Service returned status: {response.status_code}")
        except Exception:
            print("⚠ Service is not responding (may be starting or stopped)")

        port_file = PROJECT_ROOT / "logs" / "agent_port.txt"
        if port_file.exists():
            print(f"\nOther programs can read port from: {port_file}")
            print(f"  Example: cat {port_file}")

        return True
    else:
        print("⚠ No Agent service port found")
        print("  Service may not be running, or port file was not created")
        print("  Try starting the service: python agent.py start")
        return False
