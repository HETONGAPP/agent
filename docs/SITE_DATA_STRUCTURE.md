# Site Data Structure

每个站点（Site）的数据存储在独立的 InfluxDB bucket 中，bucket 命名格式为：`site_{site_id}`

## 数据存储架构

### Bucket 结构
- **Bucket 名称**: `site_{site_id}` (例如: `site_1`, `site_2`)
- **数据保留策略**: 30 天（可配置）
- **组织**: `bess`

## 1. 站点元数据 (sites_metadata)

**Measurement**: `sites_metadata`

### Tags
- `site_id` (string): 站点 ID

### Fields
- `exists` (boolean): 站点是否存在标记
- `site_name` (string): 站点名称
- `location` (string): 位置信息
- `timezone` (string): 时区（默认: UTC）
- `climate` (string): 气候类型
- `country` (string): 国家
- `state` (string): 州/省
- `latitude` (float): 纬度
- `longitude` (float): 经度
- `settings_json` (string): 设置信息（JSON 字符串）
- `devices_json` (string): 设备配置（JSON 字符串）

### 示例
```
sites_metadata,site_id=1 site_name="Data Center 1",location="Beijing",latitude=39.9042,longitude=116.4074,exists=true
```

## 2. 设备元数据 (devices_metadata)

**Measurement**: `devices_metadata`

### Tags
- `device_id` (string): 设备 ID
- `device_type` (string): 设备类型（BMS, PCS, EMS 等）
- `integration_name` (string): 集成名称
- `status` (string): 设备状态（ACTIVE, INACTIVE 等）
- `site_id` (string): 所属站点 ID

### Fields
- `exists` (boolean): 设备是否存在标记
- `metadata_json` (string): 设备元数据（JSON 字符串）
- `registered_at` (string): 注册时间（ISO 格式）
- `last_seen` (string): 最后活跃时间（ISO 格式）

### 示例
```
devices_metadata,device_id=BMS_001,device_type=BMS,site_id=1,status=ACTIVE exists=true,registered_at="2024-01-01T00:00:00Z"
```

## 3. 设备数据 (device_data)

**Measurement**: `device_data`

### Tags
- `device_id` (string): 设备 ID
- `device_type` (string): 设备类型
- `metric` (string): 指标名称（如: voltage, temperature, power 等）
- `site_id` (string): 所属站点 ID

### Fields
- `value` (float): 指标数值
- `unit` (string, optional): 单位
- `quality` (string, optional): 数据质量标记

### 支持的指标类型
- **电压相关**: `voltage`, `max_voltage`, `min_voltage`, `cell_voltage`
- **温度相关**: `temperature`, `max_temperature`, `min_temperature`
- **功率相关**: `active_power`, `reactive_power`, `apparent_power`
- **电池相关**: `soc` (State of Charge), `soh` (State of Health)
- **其他**: `current`, `frequency`, `efficiency` 等

### 示例
```
device_data,device_id=BMS_001,device_type=BMS,metric=voltage,site_id=1 value=48.5
device_data,device_id=BMS_001,device_type=BMS,metric=temperature,site_id=1 value=25.3
device_data,device_id=PCS_001,device_type=PCS,metric=active_power,site_id=1 value=1000.0
```

### 数组数据存储
对于数组类型的数据（如多个电池单元的电压），会存储为：
- 单个 cell 数据: `device_data,device_id=XXX,metric=cell_voltage,cell_index=0 value=3.7`
- 聚合值: `device_data,device_id=XXX,metric=cell_voltage_mean value=3.65`

## 4. 告警数据 (alarms)

**Measurement**: `alarms`

### Tags
- `alarm_id` (string): 告警 ID
- `alarm_type` (string): 告警类型
- `severity` (string): 严重程度（CRITICAL, WARNING, INFO）
- `device_id` (string, optional): 关联设备 ID
- `site_id` (string): 所属站点 ID

### Fields
- `message` (string): 告警消息
- `value` (float, optional): 触发告警的数值
- `threshold` (float, optional): 阈值
- `status` (string): 告警状态（ACTIVE, RESOLVED, ACKNOWLEDGED）
- `metadata_json` (string): 额外元数据（JSON 字符串）

### 示例
```
alarms,alarm_id=ALM_001,alarm_type=HIGH_VOLTAGE,severity=WARNING,device_id=BMS_001,site_id=1 message="Voltage exceeds threshold",value=50.5,threshold=50.0,status=ACTIVE
```

## 5. 诊断数据 (diagnostics)

**Measurement**: `diagnostics`

### Tags
- `alarm_id` (string): 关联的告警 ID
- `device_id` (string, optional): 关联设备 ID
- `site_id` (string): 所属站点 ID

### Fields
- `risk_level` (string): 风险等级（HIGH, MEDIUM, LOW）
- `summary` (string): 诊断摘要
- `explanation` (string): 技术解释
- `recommended_actions` (string): 推荐操作（JSON 字符串）
- `metadata_json` (string): 额外元数据（JSON 字符串）

### 示例
```
diagnostics,alarm_id=ALM_001,device_id=BMS_001,site_id=1 risk_level=MEDIUM,summary="Battery voltage slightly elevated"
```

## 6. BMS 数据 (bms_data)

**Measurement**: `bms_data`

### Tags
- `pack_id` (string): 电池包 ID
- `metric` (string): 指标类型（soc, soh, max_delta_v, max_voltage, min_voltage, max_temperature, min_temperature）
- `site_id` (string): 所属站点 ID

### Fields
- `value` (float): 指标数值

### 示例
```
bms_data,pack_id=PACK_001,metric=soc,site_id=1 value=85.5
bms_data,pack_id=PACK_001,metric=soh,site_id=1 value=92.3
```

## 数据查询示例

### 查询站点所有设备数据
```flux
from(bucket: "site_1")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "device_data")
  |> filter(fn: (r) => r["site_id"] == "1")
```

### 查询特定设备的电压数据
```flux
from(bucket: "site_1")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "device_data")
  |> filter(fn: (r) => r["device_id"] == "BMS_001")
  |> filter(fn: (r) => r["metric"] == "voltage")
```

### 查询活跃告警
```flux
from(bucket: "site_1")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alarms")
  |> filter(fn: (r) => r["status"] == "ACTIVE")
```

## 数据隔离

每个站点的数据完全隔离：
- ✅ 每个站点有独立的 bucket
- ✅ 所有数据都包含 `site_id` tag 用于过滤
- ✅ 删除站点时，对应的 bucket 会被删除
- ✅ 查询时自动使用站点对应的 bucket

## 数据保留策略

- **默认保留期**: 30 天
- **可配置**: 通过 `OptimizationConfig` 配置
- **自动清理**: InfluxDB 自动删除过期数据

