# InfluxDB Flux Query Examples

This document contains common Flux query examples for querying alarm data from InfluxDB.

## Basic Queries

### Query All Alarms
```flux
from(bucket: "site_1")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> sort(columns: ["_time"], desc: true)
```

### Count Total Alarms
```flux
from(bucket: "site_1")
  |> range(start: -3650d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> count()
```

### Query Recent Alarms (Last 10)
```flux
from(bucket: "site_1")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 10)
```

## Grouped Queries

### Count by Alarm Type
```flux
from(bucket: "site_1")
  |> range(start: -3650d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> group(columns: ["alarm_type"])
  |> count()
```

### Count by Severity
```flux
from(bucket: "site_1")
  |> range(start: -3650d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> group(columns: ["severity"])
  |> count()
```

### Count by Device ID
```flux
from(bucket: "site_1")
  |> range(start: -3650d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> group(columns: ["device_id"])
  |> count()
```

## Filtered Queries

### Filter by Alarm Type
```flux
from(bucket: "site_1")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> filter(fn: (r) => r["alarm_type"] == "cell_voltage_deviation")
  |> sort(columns: ["_time"], desc: true)
```

### Filter by Severity
```flux
from(bucket: "site_1")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> filter(fn: (r) => r["severity"] == "Warning")
  |> sort(columns: ["_time"], desc: true)
```

### Filter by Device ID
```flux
from(bucket: "site_1")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> filter(fn: (r) => r["device_id"] == "BMS_001")
  |> sort(columns: ["_time"], desc: true)
```

## Time Series Queries

### Alarms per Hour
```flux
from(bucket: "site_1")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> aggregateWindow(every: 1h, fn: count, createEmpty: false)
  |> sort(columns: ["_time"])
```

### Alarms per Day
```flux
from(bucket: "site_1")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> aggregateWindow(every: 1d, fn: count, createEmpty: false)
  |> sort(columns: ["_time"])
```

## Notes

- Replace `"site_1"` with your actual bucket name if different
- Adjust time ranges as needed: `-30d` (30 days), `-7d` (7 days), `-24h` (24 hours)
- Use `-3650d` for all historical data (10 years)
