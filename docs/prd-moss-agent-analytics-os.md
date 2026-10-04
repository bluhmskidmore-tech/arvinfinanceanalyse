# MOSS Agent Analytics OS PRD

本文件是旧 PRD 路径的兼容入口。产品定义和阶段目标统一维护在仓库根 [MOSS Agent Analytics OS PRD](../prd-moss-agent-analytics-os.md)，权威顺序见 [DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md#权威顺序)。本文件不另定义产品范围或执行授权。

原章节标题全部保留，供旧链接按原锚点跳转；各节链接指向根 PRD 对应正文。当前接口状态和已生效局部范围由根 PRD §17 引用的权威文档维护。

## 1. 项目定义

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#1-项目定义)。

### 1.1 系统本质

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#11-系统本质)。

### 1.2 项目目标

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#12-项目目标)。

### 1.3 非目标

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#13-非目标)。

## 2. 顶层架构决策

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#2-顶层架构决策)。

### 2.1 总体形态

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#21-总体形态)。

### 2.2 固定调用方向

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#22-固定调用方向)。

### 2.3 ADR

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#23-adr)。

## 3. 技术栈冻结

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#3-技术栈冻结)。

### 3.1 前端

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#31-前端)。

### 3.2 后端

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#32-后端)。

### 3.3 存储与队列

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#33-存储与队列)。

### 3.4 数据源接入

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#34-数据源接入)。

## 4. 目标目录结构

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#4-目标目录结构)。

## 5. 层级职责

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#5-层级职责)。

### 5.1 api/

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#51-api)。

### 5.2 services/

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#52-services)。

### 5.3 core_finance/

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#53-core_finance)。

### 5.4 repositories/

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#54-repositories)。

### 5.5 tasks/

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#55-tasks)。

### 5.6 governance/

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#56-governance)。

## 6. 数据分层

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#6-数据分层)。

### 6.1 PostgreSQL：事务与治理

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#61-postgresql事务与治理)。

### 6.2 DuckDB：分析与物化

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#62-duckdb分析与物化)。

### 6.3 对象存储

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#63-对象存储)。

### 6.4 正式真相边界

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#64-正式真相边界)。

## 7. 缓存栈

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#7-缓存栈)。

### 7.1 分层

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#71-分层)。

### 7.2 失效驱动

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#72-失效驱动)。

### 7.3 强缓存键

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#73-强缓存键)。

### 7.4 DuckDB 单写者

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#74-duckdb-单写者)。

## 8. 外部数据平面

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#8-外部数据平面)。

### 8.1 Choice

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#81-choice)。

### 8.2 AkShare

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#82-akshare)。

### 8.3 外部数据接入路径

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#83-外部数据接入路径)。

### 8.4 外部数据降级

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#84-外部数据降级)。

## 9. result_meta 契约

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#9-result_meta-契约)。

## 10. Agent 栈

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#10-agent-栈)。

### 10.1 基本原则

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#101-基本原则)。

### 10.2 Agent 工具

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#102-agent-工具)。

### 10.3 Agent 输出硬要求

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#103-agent-输出硬要求)。

## 11. API 与服务面

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#11-api-与服务面)。

### 11.1 API 分类

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#111-api-分类)。

### 11.2 服务面原则

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#112-服务面原则)。

## 12. 前端工作台

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#12-前端工作台)。

## 13. 部署栈

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#13-部署栈)。

### 13.1 开发环境

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#131-开发环境)。

### 13.2 生产一期

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#132-生产一期)。

### 13.3 生产二期

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#133-生产二期)。

## 14. 实施阶段

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#14-实施阶段)。

### Phase 1

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#phase-1)。

### Phase 2

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#phase-2)。

### Phase 3

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#phase-3)。

### Phase 4

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#phase-4)。

### Phase 5

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#phase-5)。

## 15. 风险与缓解

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#15-风险与缓解)。

### 风险 1

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#风险-1)。

### 风险 2

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#风险-2)。

### 风险 3

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#风险-3)。

### 风险 4

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#风险-4)。

### 风险 5

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#风险-5)。

## 16. 禁止事项

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#16-禁止事项)。

## 17. 当前执行边界

正文见[根 PRD 对应章节](../prd-moss-agent-analytics-os.md#17-首轮实施边界)。
