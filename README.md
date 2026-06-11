# Information Entry Agent

一个面向信息录入场景的多 Agent 后端项目，目标是把传统表单录入拆解成更自然的对话式流程：用户可以先说需求，系统再逐步完成字段抽取、企业名称确认、地址解析和结构化提交。

这个项目不是单纯的聊天机器人，也不是静态表单包装。它更接近一个围绕“录入”任务设计的工作流代理：主流程负责多轮采集和状态推进，子流程负责处理企业名称与地点这种高歧义字段，最后再回到结构化数据提交。

## 项目定位

适合展示以下能力：

- 面向业务录入场景的 Agent 工作流设计
- `LLM + 规则 + 外部服务` 的混合编排
- 面向真实字段模型的多轮对话状态管理
- 可运行的 API、Playground、测试与评估脚本

## 核心能力

### 1. Distributor Agent

主信息录入代理，负责承接用户输入并维护录入状态。

- 支持对话式字段采集与增量更新
- 支持结构化 patch 写回
- 支持字段校验、必填检查与下一步引导
- 支持企业确认流、地址确认流的切换与恢复
- 支持实时语音识别 WebSocket 接口

对应入口：

- `POST /api/agent/distributors/chat`
- `PATCH /api/agent/distributors/fields`
- `POST /api/agent/distributors/company/sync`
- `POST /api/agent/distributors/location/sync`

### 2. Company Agent

企业名称确认代理，处理“名称不完整、可能有多个候选、需要工商校验”的问题。

- 先做企业名称候选发现
- 接入启信宝做企业检索与校验
- 在候选冲突时结合联网搜索与 LLM 交叉判断
- 支持候选选择与手工确认

对应入口：

- `POST /api/company/resolve`
- `POST /api/qixin/companies/search`

### 3. Location Agent

地点解析代理，处理“地址模糊、缺少门牌、需要附近候选或地图搜索”的问题。

- 支持当前位置附近候选推荐
- 支持基于文本的地址搜索
- 支持模糊地址补全与候选确认
- 支持用户手工确认地址
- 集成高德地图搜索能力

对应入口：

- `POST /api/location-agent/resolve`
- `POST /api/location-agent/nearby`
- `POST /api/location-agent/search`

## 项目亮点

- 不是把 LLM 直接塞进接口，而是围绕录入任务设计了主流程与子流程的状态机。
- 企业与地址这两类高歧义字段被单独拆成 Agent，降低主流程复杂度。
- 同时使用规则抽取、LLM 判断、外部企业数据与地图能力，避免单一策略失真。
- 仓库中包含 Playground、接口层、测试用例和评估脚本，完整度高于单纯 demo。

## 技术栈

- 后端框架：`FastAPI`
- 模型接入：`OpenAI Compatible API`、`Qwen`、`DeepSeek`
- 状态与数据基础设施：`Redis`、`MySQL`
- 外部服务：`启信宝`、`高德地图`
- 工程化：`Docker Compose`、`Pytest`、`Ruff`

## 系统入口

服务启动后可直接访问：

- 健康检查：`GET /healthz`
- Distributor Playground：`/playground/distributor-agent`
- Location Playground：`/playground/location-agent`

默认本地地址：

```text
http://localhost:8000
```

## 快速启动

### 1. 准备环境变量

复制示例配置：

```bash
cp .env.example .env
```

至少需要根据实际情况补充以下配置：

- `OPENAI_API_KEY`
- `QIXIN_APP_KEY`
- `QIXIN_SECRET_KEY`
- `AMAP_WEB_SERVICE_KEY`
- `AMAP_JS_API_KEY`
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `REDIS_PASSWORD`

### 2. 使用 Docker Compose 启动

```bash
docker compose up --build
```

启动后默认会拉起：

- `app`：FastAPI 服务
- `mysql`：MySQL 8
- `redis`：Redis 7

### 3. 打开 Playground

在浏览器访问：

```text
http://localhost:8000/playground/distributor-agent
http://localhost:8000/playground/location-agent
```

## 代码结构

```text
app/
  api/                FastAPI 路由层
  agent/              主录入 Agent：状态、抽取、校验、对话策略
  company_agent/      企业名称确认 Agent
  location_agent/     地址解析 Agent
  integrations/       外部服务集成
  playground/         本地交互页面
tests/                单元测试与接口测试
evals/                评估数据与评测脚本
impl-api/             设计与实现过程文档
```

## 当前实现状态

当前仓库已经具备可运行的后端骨架与核心流程，但仍然保持明显的迭代痕迹，属于“可演示、可继续扩展”的工程状态。

- 主录入流程、企业确认流、地址确认流已经拆分完成
- API、Playground、测试与评估脚本已落地
- 创建经销商的最终后端提交目前仍使用 mock adapter 占位
- 部分能力依赖外部密钥与上游服务可用性

## 后续可扩展方向

- 引入更稳定的生产级创建/更新接口
- 增强多轮对话策略与纠错能力
- 补充更完整的评估集与自动化回归机制
- 增加可观测性、审计日志与失败恢复能力

## 适合在 GitHub 上怎么理解这个项目

如果你是访客或面试官，可以把它理解为一个围绕“信息录入”任务搭建的多 Agent 实验型工程。重点不在单个模型调用，而在于：

- 如何把复杂录入任务拆成主流程与专门子流程
- 如何让 LLM、规则和外部服务一起工作
- 如何把对话结果稳定落到结构化字段上

这也是这个仓库最值得看的部分。
