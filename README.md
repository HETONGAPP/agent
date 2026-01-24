# BESS Alarm Diagnostic Agent

A Battery Energy Storage System (BESS) alarm diagnostic agent that automatically analyzes alarm data and generates technical explanations, risk ratings, and recommended actions.

## Quick Start

### Installation

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp env.example .env
# Edit .env file with necessary configurations
```

### Start

```bash
# Using Docker Compose (recommended)
cd docker
docker-compose up -d

# Or using CLI tool
python scripts/agent.py start
```

### Check Status

```bash
python scripts/agent.py status
# or
curl http://localhost:8000/health
```

## Configuration

Main environment variables (`.env` file):

- `DEBUG` - Debug mode switch (default: `false`)
  - Set to `true` to enable debug mode: Shows all logs including INFO and WARNING
  - Set to `false` to disable debug mode: Only shows ERROR and above (cleaner output)
  - Example: `DEBUG=true` or `DEBUG=false`
- `OPENAI_API_KEY` - LLM API key
- `INFLUXDB_TOKEN` - InfluxDB access token
- `INFLUXDB_URL` - InfluxDB URL (default: http://localhost:8086)
- `GRAFANA_API_KEY` - Grafana API key
- `SMTP_USER` / `SMTP_PASSWORD` - Email service configuration

## Common Commands

```bash
# Service management
python scripts/agent.py start      # Start service
python scripts/agent.py stop       # Stop service
python scripts/agent.py status     # Check status

# Interactive mode
python scripts/agent.py interactive

# Testing
python scripts/agent.py test
```

## Frontend

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Frontend will be available at http://localhost:5173 (or the port shown in terminal).

### Build

```bash
npm run build
```

## Device Simulator

The device simulator generates and publishes BMS/PCS device data via MQTT for testing.

### Usage

```bash
# Simulate BMS device
python -m src.simulator.device_simulator --type BMS --device-id BMS_001

# Simulate PCS device
python -m src.simulator.device_simulator --type PCS --device-id PCS_001

# With custom site
python -m src.simulator.device_simulator --type BMS --device-id BMS_001 --site-id SITE_002 --site-name "Data Center 2"

# With custom interval (seconds)
python -m src.simulator.device_simulator --type BMS --device-id BMS_001 --interval 10
```

### Configuration

Set MQTT broker settings in `.env`:
- `MQTT_BROKER_URL` - MQTT broker URL (default: mqtt://localhost:1883)
- `MQTT_USERNAME` - MQTT username (optional)
- `MQTT_PASSWORD` - MQTT password (optional)

## Access URLs

- **Agent API**: http://localhost:8000/docs
- **Frontend**: http://localhost:5173
- **Grafana**: http://localhost:3000
- **InfluxDB**: http://localhost:8086

## Project Structure

```
src/
├── agent/          # Main service
├── collector/       # Data collection
├── rule_engine/     # Rule engine
├── llm_diagnostic/  # LLM diagnostic service
├── grafana/         # Grafana integration
├── email/           # Email service
└── simulator/       # Device simulator
```

---

**Note**: The `.env` file contains sensitive information and should not be committed to Git.
