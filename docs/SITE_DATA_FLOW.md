# Site Data Flow Diagram

## 站点数据存储架构流程图

```mermaid
graph TB
    subgraph "Site Container Architecture"
        Site[站点 Site ID: 1] --> Bucket[InfluxDB Bucket: site_1]
        
        Bucket --> Metadata[站点元数据<br/>sites_metadata]
        Bucket --> DeviceMeta[设备元数据<br/>devices_metadata]
        Bucket --> DeviceData[设备数据<br/>device_data]
        Bucket --> Alarms[告警数据<br/>alarms]
        Bucket --> Diagnostics[诊断数据<br/>diagnostics]
        Bucket --> BMSData[BMS数据<br/>bms_data]
    end
    
    subgraph "数据写入流程"
        API[API请求/MQTT消息] --> Agent[Agent Service]
        Agent --> SiteManager[Site Manager]
        SiteManager --> InfluxClient[InfluxDB Client]
        InfluxClient --> Bucket
    end
    
    subgraph "数据查询流程"
        Query[查询请求] --> SiteManager
        SiteManager --> InfluxClient
        InfluxClient --> Bucket
        Bucket --> Result[查询结果]
    end
    
    style Site fill:#e1f5ff
    style Bucket fill:#fff4e1
    style Metadata fill:#e8f5e9
    style DeviceMeta fill:#e8f5e9
    style DeviceData fill:#e8f5e9
    style Alarms fill:#ffebee
    style Diagnostics fill:#f3e5f5
```

## 站点数据结构关系图

```mermaid
erDiagram
    SITE ||--o{ DEVICE : "has"
    SITE ||--o{ ALARM : "generates"
    SITE ||--o{ DIAGNOSTIC : "has"
    SITE ||--o{ DEVICE_DATA : "contains"
    SITE ||--o{ BMS_DATA : "contains"
    
    DEVICE ||--o{ DEVICE_DATA : "produces"
    DEVICE ||--o{ ALARM : "triggers"
    ALARM ||--o| DIAGNOSTIC : "analyzed_by"
    
    SITE {
        string site_id PK
        string site_name
        string location
        float latitude
        float longitude
        string timezone
        json settings
        json devices_config
    }
    
    DEVICE {
        string device_id PK
        string device_type
        string site_id FK
        string status
        datetime registered_at
        datetime last_seen
    }
    
    DEVICE_DATA {
        string device_id FK
        string metric
        float value
        datetime timestamp
        string site_id FK
    }
    
    ALARM {
        string alarm_id PK
        string alarm_type
        string severity
        string device_id FK
        string site_id FK
        string status
        datetime timestamp
    }
    
    DIAGNOSTIC {
        string alarm_id FK
        string device_id FK
        string site_id FK
        string risk_level
        string summary
        string explanation
    }
    
    BMS_DATA {
        string pack_id
        string metric
        float value
        string site_id FK
        datetime timestamp
    }
```

## 数据写入详细流程

```mermaid
sequenceDiagram
    participant Client as 客户端/MQTT
    participant API as FastAPI
    participant Agent as Agent Service
    participant SiteMgr as Site Manager
    participant Influx as InfluxDB Client
    participant Bucket as Site Bucket
    
    Client->>API: POST /api/v1/sites (创建站点)
    API->>SiteMgr: create_site(site_data)
    SiteMgr->>Influx: save_site(site_data)
    Influx->>Bucket: 检查 bucket 是否存在
    alt bucket 不存在
        Influx->>Bucket: 创建 bucket (site_1)
    end
    Influx->>Bucket: 写入 sites_metadata
    Bucket-->>Influx: 成功
    Influx-->>SiteMgr: 成功
    SiteMgr-->>API: 成功
    API-->>Client: 201 Created
    
    Client->>API: MQTT 消息 (设备数据)
    API->>Agent: process_device_data()
    Agent->>SiteMgr: 获取站点信息
    SiteMgr-->>Agent: 站点配置
    Agent->>Influx: write_device_data()
    Influx->>Bucket: 写入 device_data
    Note over Influx,Bucket: 自动添加 site_id tag
    Bucket-->>Influx: 成功
    Influx-->>Agent: 成功
    Agent->>Agent: 检查告警规则
    alt 触发告警
        Agent->>Influx: write_alarm()
        Influx->>Bucket: 写入 alarms
        Agent->>Agent: 生成诊断
        Agent->>Influx: write_diagnostic()
        Influx->>Bucket: 写入 diagnostics
    end
```

## 数据查询流程

```mermaid
flowchart TD
    Start[查询请求] --> Check{查询类型}
    
    Check -->|站点列表| QuerySites[查询所有站点]
    Check -->|站点详情| QuerySite[查询单个站点]
    Check -->|设备数据| QueryDevices[查询设备数据]
    Check -->|告警数据| QueryAlarms[查询告警]
    Check -->|时间序列| QueryTimeSeries[查询时间序列]
    
    QuerySites --> ListBuckets[列出所有 site_* buckets]
    ListBuckets --> GetMetadata[获取 sites_metadata]
    GetMetadata --> ReturnSites[返回站点列表]
    
    QuerySite --> GetBucket[获取 site_{id} bucket]
    GetBucket --> GetSiteMeta[查询 sites_metadata]
    GetSiteMeta --> ReturnSite[返回站点信息]
    
    QueryDevices --> GetDeviceBucket[获取站点 bucket]
    GetDeviceBucket --> FilterDevice[过滤 device_data]
    FilterDevice --> Aggregate[聚合数据]
    Aggregate --> ReturnDevices[返回设备数据]
    
    QueryAlarms --> GetAlarmBucket[获取站点 bucket]
    GetAlarmBucket --> FilterAlarm[过滤 alarms]
    FilterAlarm --> SortAlarm[排序和分页]
    SortAlarm --> ReturnAlarms[返回告警列表]
    
    QueryTimeSeries --> GetTSBucket[获取站点 bucket]
    GetTSBucket --> FilterTS[过滤 device_data]
    FilterTS --> Window[时间窗口聚合]
    Window --> NumericFilter[过滤数值字段]
    NumericFilter --> MeanAgg[mean 聚合]
    MeanAgg --> ReturnTS[返回时间序列]
    
    ReturnSites --> End[返回结果]
    ReturnSite --> End
    ReturnDevices --> End
    ReturnAlarms --> End
    ReturnTS --> End
```

## 站点数据隔离机制

```mermaid
graph LR
    subgraph "Site 1"
        S1[Site 1] --> B1[Bucket: site_1]
        B1 --> D1[设备数据]
        B1 --> A1[告警数据]
        B1 --> M1[元数据]
    end
    
    subgraph "Site 2"
        S2[Site 2] --> B2[Bucket: site_2]
        B2 --> D2[设备数据]
        B2 --> A2[告警数据]
        B2 --> M2[元数据]
    end
    
    subgraph "Site N"
        SN[Site N] --> BN[Bucket: site_N]
        BN --> DN[设备数据]
        BN --> AN[告警数据]
        BN --> MN[元数据]
    end
    
    Query[查询请求<br/>site_id=1] --> B1
    Query2[查询请求<br/>site_id=2] --> B2
    
    style S1 fill:#e1f5ff
    style S2 fill:#e1f5ff
    style SN fill:#e1f5ff
    style B1 fill:#fff4e1
    style B2 fill:#fff4e1
    style BN fill:#fff4e1
```

## 数据生命周期

```mermaid
stateDiagram-v2
    [*] --> 数据写入: API/MQTT
    数据写入 --> 站点Bucket: 存储到 site_{id}
    站点Bucket --> 数据查询: 实时查询
    站点Bucket --> 数据聚合: 时间窗口聚合
    站点Bucket --> 数据清理: 30天后自动删除
    
    数据查询 --> [*]
    数据聚合 --> [*]
    数据清理 --> [*]
    
    站点删除 --> 删除Bucket: 删除整个 bucket
    删除Bucket --> [*]
```

