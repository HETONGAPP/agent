"""
CLI utility functions
"""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def show_pids():
    """Show all service PIDs"""
    print_header("Service Process IDs (PIDs)")

    all_pids = []

    # Check PID file
    pid_file = PROJECT_ROOT / "logs" / "agent_service.pid"
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
                all_pids.append(("Agent Service (from PID file)", pid))
        except (ValueError, FileNotFoundError):
            pass

    # Find agent processes
    print("1. Agent Services:")
    from .service import find_agent_processes

    try:
        found_pids = find_agent_processes()

        if found_pids:
            agent_pids = []
            for pid in found_pids:
                try:
                    proc_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "args="],
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )
                    cmd_line = (
                        proc_result.stdout.strip()
                        if proc_result.returncode == 0
                        else "N/A"
                    )

                    port = "unknown"
                    if "--port" in cmd_line:
                        parts = cmd_line.split()
                        try:
                            port_idx = parts.index("--port")
                            if port_idx + 1 < len(parts):
                                port = parts[port_idx + 1]
                        except (ValueError, IndexError):
                            pass

                    agent_pids.append((pid, port, cmd_line))
                except Exception:
                    agent_pids.append((pid, "unknown", "N/A"))

            for pid, port, cmd_line in agent_pids:
                print(f"   PID: {pid:>6} | Port: {port:>5} | {cmd_line[:60]}")
                if not any(p[1] == pid for p in all_pids):
                    all_pids.append(("Agent Service", pid))
        else:
            print("   ⚠ No Agent services found")
    except Exception as e:
        print(f"   ⚠ Error checking processes: {e}")

    # Docker containers
    print("\n2. Docker Containers:")
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            containers = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        container_id = parts[0]
                        name = parts[1]
                        status = parts[2] if len(parts) > 2 else ""
                        pid_result = subprocess.run(
                            ["docker", "inspect", "-f", "{{.State.Pid}}", container_id],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        pid = (
                            pid_result.stdout.strip()
                            if pid_result.returncode == 0
                            else "N/A"
                        )
                        containers.append((name, container_id[:12], pid, status))

            if containers:
                print(
                    f"   {'Name':<20} {'Container ID':<15} {'Host PID':<12} {'Status'}"
                )
                print("   " + "-" * 75)
                for name, cid, pid, status in containers:
                    print(f"   {name:<20} {cid:<15} {pid:<12} {status[:30]}")
                    if pid != "N/A" and pid.isdigit():
                        try:
                            host_pid = int(pid)
                            all_pids.append((f"Docker: {name}", host_pid))
                        except ValueError:
                            pass
            else:
                print("   ⚠ No Docker containers found")
        else:
            print("   ⚠ Docker not available")
    except Exception as e:
        print(f"   ⚠ Error checking Docker: {e}")

    # Summary
    print("\n3. Summary:")
    if all_pids:
        print(f"   Total services found: {len(all_pids)}")
        print(f"   {'Service':<30} {'PID':<10} {'Status'}")
        print("   " + "-" * 50)
        for name, pid in all_pids:
            if name.startswith("Docker:"):
                status = "✓ (managed by Docker)"
            else:
                try:
                    import os

                    os.kill(pid, 0)
                    status = "✓ Running"
                except (ProcessLookupError, OSError):
                    status = "✗ Stopped"
                except PermissionError:
                    status = "? (no permission)"
            print(f"   {name:<30} {pid:<10} {status}")
    else:
        print("   ⚠ No services found")
