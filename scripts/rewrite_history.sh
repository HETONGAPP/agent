#!/bin/bash
# Rewrite git history with conventional commits

set -e

cd "$(dirname "$0")/.."

# Get the root commit
ROOT_COMMIT=$(git log --reverse --format="%H" | head -1)

# Create a new orphan branch
git checkout --orphan new-main

# Remove all files from staging
git rm -rf --cached . 2>/dev/null || true

# Commit sequence with conventional commits (no body)
# 1. Initial project setup
git add README.md requirements.txt env.example .gitignore Makefile
git commit -m "chore: initial project setup"

# 2. Core infrastructure
git add src/utils/ src/core/database.py src/core/event_bus.py
git commit -m "feat: add core infrastructure and database layer"

# 3. Storage layer
git add src/storage/
git commit -m "feat: implement InfluxDB storage layer with optimization"

# 4. Models
git add src/models/
git commit -m "feat: add data models for devices, alarms and diagnostics"

# 5. MQTT integration
git add src/mqtt/
git commit -m "feat: implement MQTT client and message handler"

# 6. Data collection
git add src/collector/
git commit -m "feat: add data collection service"

# 7. Integration framework
git add src/core/integration*.py src/core/device_*.py src/core/data_*.py
git commit -m "feat: implement integration framework and device management"

# 8. BMS integration
git add src/integrations/bms/
git commit -m "feat: add BMS integration"

# 9. PCS integration
git add src/integrations/pcs/
git commit -m "feat: add PCS integration"

# 10. Rule engine
git add src/rule_engine/
git commit -m "feat: implement rule engine for alarm processing"

# 11. LLM diagnostic service
git add src/llm_diagnostic/
git commit -m "feat: add LLM-based diagnostic service"

# 12. Diagnostic agent framework
git add src/diagnostic_agent/
git commit -m "feat: implement diagnostic agent framework with multiple agents"

# 13. Email service
git add src/email/ templates/email/
git commit -m "feat: add email notification service"

# 14. Grafana integration
git add src/grafana/
git commit -m "feat: add Grafana webhook and annotation integration"

# 15. Agent service and routes
git add src/agent/
git commit -m "feat: implement FastAPI agent service with REST and WebSocket APIs"

# 16. Configuration files
git add config/
git commit -m "feat: add configuration files for rules and integrations"

# 17. Prompts
git add prompts/
git commit -m "feat: add LLM prompt templates"

# 18. CLI tools
git add scripts/
git commit -m "feat: add CLI tools for service management"

# 19. Device simulator
git add src/simulator/
git commit -m "feat: add device simulator for BMS and PCS testing"

# 20. Frontend
git add frontend/
git commit -m "feat: add React frontend with TypeScript and Tailwind CSS"

# 21. Docker setup
git add docker/
git commit -m "feat: add Docker configuration"

# 22. Tests
git add tests/
git commit -m "test: add unit and integration tests"

# 23. Documentation
git add docs/ *.md
git commit -m "docs: add project documentation"

# Replace main branch
git branch -D main 2>/dev/null || true
git branch -m main

echo "History rewritten successfully!"
echo "To push: git push -f origin main"


