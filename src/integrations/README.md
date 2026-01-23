# Device Integration Module

This directory contains integration implementations for all device types. Each device type has its own independent folder containing all related code for that device type.

## Directory Structure

```
integrations/
├── bms/              # BMS (Battery Management System) Integration
│   ├── models.py     # BMS data models
│   ├── collector.py  # BMS data collector
│   └── integration.py # BMS integration implementation
└── pcs/              # PCS (Power Conversion System) Integration
    ├── models.py     # PCS data models
    ├── collector.py  # PCS data collector
    └── integration.py # PCS integration implementation
```

## Design Principles

1. **Independence**: Code for each device type is in its own folder, isolated from others
2. **Completeness**: Each integration contains all related content for that device type (data models, collector, configuration, etc.)
3. **Unified Interface**: All integrations implement the `DeviceIntegration` interface
4. **Configuration Separation**: Each integration's configuration is in `config/integrations/{device_type}/` directory

## Adding New Integration

To add a new device type integration:

1. Create a new folder under `src/integrations/` (e.g., `ups/`)
2. Create the following files:
   - `models.py` - Define data models for that device type
   - `collector.py` - Implement data collection logic and integration class
   - `integration.py` - Export integration class
   - `__init__.py` - Module exports
3. Add creation logic in `src/core/integration_factory.py`
4. Create configuration file under `config/integrations/{device_type}/`

## Examples

### BMS Integration

```python
from src.integrations.bms import BMSIntegration, BMSData, BMSCollector
from src.core import IntegrationConfig
from src.models.device_data import DeviceType

# Create configuration
config = IntegrationConfig(
    enabled=True,
    device_type=DeviceType.BMS,
    api_url="http://bms-api:8080",
    api_key="your-api-key"
)

# Create integration
integration = BMSIntegration(config)

# Use integration
device_data = await integration.get_device_data("BMS_001")
alarms = await integration.collect_alarms()
```

### PCS Integration

```python
from src.integrations.pcs import PCSIntegration, PCSData, PCSCollector
from src.core import IntegrationConfig
from src.models.device_data import DeviceType

# Create configuration
config = IntegrationConfig(
    enabled=True,
    device_type=DeviceType.PCS,
    api_url="http://pcs-api:8080",
    api_key="your-api-key"
)

# Create integration
integration = PCSIntegration(config)

# Use integration
device_data = await integration.get_device_data("PCS_001")
alarms = await integration.collect_alarms()
```

## Configuration

Each integration's configuration is in `config/integrations/{device_type}/config.yaml`.

Configuration example (BMS):

```yaml
enabled: true
device_type: BMS
api_url: ${BMS_API_URL}
api_key: ${BMS_API_KEY}
interval: 30
timeout: 10
metadata:
  pack_id_format: "PACK_{device_id}"
```

## Advantages

- **Modularity**: Code for each device type is independent and easy to maintain
- **Extensibility**: Adding new device types only requires creating a new folder
- **Decoupling**: Core code only depends on interfaces, not specific implementations
- **Centralized Configuration**: Each integration's configuration is in its own configuration file
