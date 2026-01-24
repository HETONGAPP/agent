#!/usr/bin/env python3
"""Complete git history rewrite with conventional commits"""

import subprocess
import os
import sys

def run_cmd(cmd, check=True):
    """Run shell command"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running: {cmd}")
        print(result.stderr)
        sys.exit(1)
    return result

# Change to project root
os.chdir(os.path.dirname(os.path.dirname(__file__)))

# Commits to create
commits = [
    ("feat: implement InfluxDB storage layer with optimization", ["src/storage/"]),
    ("feat: add data models for devices, alarms and diagnostics", ["src/models/"]),
    ("feat: implement MQTT client and message handler", ["src/mqtt/"]),
    ("feat: add data collection service", ["src/collector/"]),
    ("feat: implement integration framework and device management", [
        "src/core/integration_factory.py",
        "src/core/integration_manager.py",
        "src/core/integration_registry.py",
        "src/core/integration_service_client.py",
        "src/core/integration_service_registry.py",
        "src/core/integration.py",
        "src/core/device_discovery.py",
        "src/core/device_registry.py",
        "src/core/data_collection_service.py",
        "src/core/data_flow_tracker.py",
    ]),
    ("feat: add BMS integration", ["src/integrations/bms/"]),
    ("feat: add PCS integration", ["src/integrations/pcs/"]),
    ("feat: implement rule engine for alarm processing", ["src/rule_engine/"]),
    ("feat: add LLM-based diagnostic service", ["src/llm_diagnostic/"]),
    ("feat: implement diagnostic agent framework with multiple agents", ["src/diagnostic_agent/"]),
    ("feat: add email notification service", ["src/email/", "templates/email/"]),
    ("feat: add Grafana webhook and annotation integration", ["src/grafana/"]),
    ("feat: implement FastAPI agent service with REST and WebSocket APIs", ["src/agent/"]),
    ("feat: add configuration files for rules and integrations", ["config/"]),
    ("feat: add LLM prompt templates", ["prompts/"]),
    ("feat: add CLI tools for service management", ["scripts/"]),
    ("feat: add device simulator for BMS and PCS testing", ["src/simulator/"]),
    ("feat: add React frontend with TypeScript and Tailwind CSS", ["frontend/"]),
    ("feat: add Docker configuration", ["docker/"]),
    ("test: add unit and integration tests", ["tests/"]),
    ("docs: add project documentation", ["docs/", "*.md"]),
]

print("Continuing git history rewrite...")

for msg, paths in commits:
    # Add files
    files_to_add = []
    for path in paths:
        if os.path.exists(path):
            files_to_add.append(path)
    
    if not files_to_add:
        print(f"Skipping {msg} - no files found")
        continue
    
    # Add files
    run_cmd(f"git add {' '.join(files_to_add)}", check=False)
    
    # Check if there are changes
    result = run_cmd("git status --short", check=False)
    if not result.stdout.strip():
        print(f"Skipping {msg} - no changes")
        continue
    
    # Commit
    run_cmd(f'git commit -m "{msg}"')
    print(f"✓ {msg}")

# Replace main branch
print("\nReplacing main branch...")
run_cmd("git branch -D main", check=False)
run_cmd("git branch -m main")
print("✓ History rewrite completed!")
print("\nTo push: git push -f origin main")


