# 数据中心地图功能说明

## 🎯 功能概述

前端已重新设计为以数据中心（Data Center）为核心的地图视图架构，支持：

1. **地图视图** - 显示所有站点在地图上的位置
2. **站点管理** - 手动添加站点，配置站点信息
3. **设备管理** - 为每个站点添加不同品牌的设备
4. **站点详情** - 点击站点查看详细信息

## 📁 新增文件

### API 和 Store
- `src/api/sites.ts` - 站点管理 API 客户端
- `src/store/useSiteStore.ts` - 站点状态管理 Store

### 组件
- `src/components/map/DataCenterMap.tsx` - 数据中心地图组件
- `src/components/map/SiteMarker.tsx` - 站点标记组件（可点击）
- `src/components/sites/AddSiteForm.tsx` - 添加站点表单
- `src/components/sites/AddDeviceForm.tsx` - 添加设备表单

### 页面
- `src/pages/DataCenterMap.tsx` - 数据中心地图主页面
- `src/pages/SiteDetails.tsx` - 站点详情页面

## 🗺️ 地图功能

### 1. 地图视图
- 使用 Leaflet 地图库
- 显示所有站点位置
- 支持点击地图添加新站点（自动获取坐标）
- 站点标记可点击，显示站点信息

### 2. 站点标记
- 自定义图标显示站点
- 弹出窗口显示站点基本信息
- 点击"View Details"跳转到站点详情页

### 3. 添加站点
- 点击"Add Site"按钮或点击地图
- 填写站点信息：
  - Site ID（必填）
  - Site Name（必填）
  - Location（位置描述）
  - Latitude/Longitude（经纬度，点击地图自动填充）
  - Timezone（时区）
  - Climate（气候）

## 📍 站点详情

### 1. **Overview 标签页**
   - 站点基本信息
   - 站点配置信息
   - 快速统计

### 2. **Devices 标签页**
   - 显示站点下的所有设备
   - 支持添加新设备
   - 设备信息包括：
     - Device ID
     - Device Type（BMS, PCS, TMS 等）
     - Brand/Manufacturer（品牌）
     - Model（型号）
     - Status（状态）
     - Integration Service（集成服务）

### 3. **Rules 标签页**
   - 显示站点特定规则
   - 规则配置（待实现）

### 4. **Settings 标签页**
   - 站点设置配置（待实现）

## 🚀 使用方式

### 1. 访问地图页面
```
导航栏 → Data Center (🗺️)
或直接访问：/datacenter
```

### 2. 添加站点
1. 点击"Add Site"按钮
2. 或直接点击地图上的位置（自动填充坐标）
3. 填写站点信息
4. 点击"Create Site"

### 3. 查看站点详情
1. 在地图上点击站点标记
2. 点击弹出窗口中的"View Details"
3. 或直接访问：`/datacenter/sites/{site_id}`

### 4. 添加设备到站点
1. 进入站点详情页
2. 切换到"Devices"标签
3. 点击"Add Device"按钮
4. 填写设备信息（包括品牌、型号等）
5. 点击"Add Device"

## 🔧 技术实现

### 地图库
- **Leaflet** - 开源地图库
- **react-leaflet** - React 绑定
- 使用 OpenStreetMap 瓦片

### 状态管理
- **Zustand** - 站点状态管理
- 支持实时数据更新（WebSocket）

### 路由
- `/datacenter` - 数据中心地图主页面
- `/datacenter/sites/:siteId` - 站点详情页面

## ⚠️ 待实现功能

1. **站点创建 API** - 后端需要实现站点创建 API
2. **设备添加 API** - 后端需要实现设备添加到站点的 API
3. **站点编辑** - 支持编辑站点信息
4. **站点删除** - 支持删除站点
5. **设备品牌管理** - 设备品牌和型号的完整管理
6. **地图样式** - 自定义地图样式和主题

## 📝 注意事项

1. **站点坐标**：如果站点没有坐标，会使用默认位置（北京）
2. **设备关联**：设备通过 `metadata.site_id` 字段关联到站点
3. **实时更新**：站点数据支持 WebSocket 实时更新
4. **地图交互**：点击地图可以获取坐标并添加站点

## 🎨 UI 特性

- 响应式设计，支持不同屏幕尺寸
- 深色主题，符合现有设计风格
- 流畅的动画和过渡效果
- 直观的交互体验











