# 经销商名称 Agent 接入主 Agent 摘要（2026-06-09）

## 目标

本轮工作的目标是把 `.worktrees/location-agent` 里的独立 `company-agent` 接入主 `distributor-agent`，实现下面这条链路：

1. 主 agent 在抽取到 `main_info.distributorName` 后，不直接写入主状态。
2. 先切到经销商名称确认子流程。
3. 调用经销商名称 agent 做名称识别。
4. 把启信宝候选列表返回给前端。
5. 前端用下拉列表展示候选；如果没有匹配项，允许继续输入名称。
6. 前端继续输入时，实时调用启信宝搜索接口拿候选。
7. 用户确认后，再把最终 `distributorName` 回写到主 agent 状态，恢复主流程。

当前实现已经完成。

## 当前代码位置

本次改动主要都在 `.worktrees/location-agent`：

- 主 agent
  - `app/agent/service.py`
  - `app/agent/models.py`
  - `app/api/chat.py`
- 公司名称 agent
  - `app/company_agent/service.py`
  - `app/company_agent/llm.py`
  - `app/company_agent/prompts.py`
- 前端联调页
  - `app/playground/distributor_chat/index.html`
- 测试
  - `tests/test_agent_company_integration.py`
  - `tests/test_api_chat.py`
  - `tests/test_company_agent.py`
  - `tests/test_playground.py`

## 当前主流程行为

### 1. 主 agent 识别到经销商名称后进入 `company_flow`

`app/agent/models.py` 新增了：

- `ActiveFlow.COMPANY`
- `CompanyFlowStatus`
- `CompanyFlowSnapshot`
- `CompanyFlowSyncRequest`
- `CompanyCommitRequest`
- `CompanySearchRequest`

`ChatResponse` 现在会返回：

- `active_flow`
- `company_flow`
- `location_flow`

### 2. 主 agent 不直接落库 `distributorName`

`app/agent/service.py` 里新增了 `_split_company_patch()`。

行为：

- 从抽取 patch 中把 `main_info.distributorName` 拆出来
- 其余 `main_info` / `contacts` / `sites` 正常保留
- `distributorName` 进入 `company_flow`

也就是说，现在主 agent 抽到：

```json
{
  "main_info": {
    "distributorName": "契胜",
    "customerMobile": "13800138000"
  }
}
```

实际会变成：

- `customerMobile` 先写入主状态
- `distributorName` 交给公司名称子流程

### 3. 主 agent 触发 `company-agent`

`AgentService._start_company_flow()` 会：

1. 调用 `CompanyAgentService.resolve(CompanyResolveRequest(user_input=...))`
2. 拿到公司识别结果
3. 把结果归一化成 `need_select`
4. 保存到 `state.company_flow.last_response`
5. 返回 `active_flow = company`

注意：这里特意做了归一化。

即使 `company-agent` 返回：

- `status = resolved`
- `company_name = 契胜科技（集团）有限公司`

主 agent 也会把它转成：

- `status = need_select`
- `candidates = [契胜科技（集团）有限公司]`

原因是产品要求是：

- “返回经过启信宝查询后的列表供用户选择”

所以主 handoff 一律按“可选择候选列表”处理，而不是自动帮用户确认。

### 4. 前端公司名称卡片

`app/playground/distributor_chat/index.html` 新增了 `company-action-card`。

卡片行为：

- 如果 `company_flow.last_response.status == need_select`
  - 渲染下拉候选框
  - 用户可点“确认所选名称”
- 如果没有理想候选
  - 可在输入框继续输入
  - 前端会 debounce 后调用实时搜索接口
- 如果拿到单一可确认候选
  - 也仍然展示成卡片确认

### 5. 实时搜索接口

主 agent 新增接口：

- `POST /api/agent/distributors/company/search`
- `POST /api/agent/distributors/company/sync`
- `POST /api/agent/distributors/company/commit`

职责：

- `company/search`
  - 前端输入框实时查启信宝候选
  - 不走 LLM，只走启信宝
- `company/sync`
  - 把前端拿到的 `company-agent` 响应同步回主 session
- `company/commit`
  - 用户确认最终名称后，写回 `main_info.distributorName`
  - 结束 `company_flow`
  - 回到主流程

## `company-agent` 当前行为

### 独立 `company-agent`

独立接口仍然在：

- `POST /api/company/resolve`

当前流程是：

1. 先让 Qwen 对用户原始输入做联网搜证
2. 从联网搜索结果提取候选公司全称
3. 逐个回查启信宝做验真
4. 如果搜证未解出，再 fallback 到原始启信宝搜索
5. 如果启信宝返回 2+ 条，再做 LLM 交叉验证

### 实时搜索接口

为了前端手动输入时更稳定，`app/company_agent/service.py` 新增了：

- `search_candidates(keyword: str)`

这个方法只做：

1. `QixinClient.adv_search(keyword)`
2. 把 `data.items` 解析成 `CompanyCandidate`
3. 返回 `need_select` 或 `need_manual_input`

它不走 LLM，专门给实时输入场景使用。

## 已验证的真实接口

### 1. 主 agent handoff

真实调用：

```bash
POST /api/agent/distributors/chat
```

输入：

```json
{
  "session_id": "live-company-main-2",
  "message": "新增经销商，经销商叫契胜，客户手机号13800138000。"
}
```

返回要点：

- `active_flow = company`
- `company_flow.status = active`
- `company_flow.last_response.status = need_select`
- 候选里有 `契胜科技（集团）有限公司`
- `state_summary.main_info` 里只有 `customerMobile`
- 还没有写入 `distributorName`

这说明主 agent 已经先进入公司名称确认子流程，而不是直接把名称落入主状态。

### 2. 实时启信宝搜索

真实调用：

```bash
POST /api/agent/distributors/company/search
```

输入：

```json
{
  "session_id": "live-company-main-1",
  "keyword": "上海码岱码网络科技"
}
```

返回要点：

- `status = need_select`
- 候选列表包含 `上海码岱码网络科技有限公司`

这说明前端手动输入实时搜索这条链路已经通了。

## 当前测试结果

本轮已跑通的核心测试：

```bash
docker compose -f docker-compose.location-agent.yml exec app python -m pytest \
  tests/test_agent_company_integration.py \
  tests/test_api_chat.py \
  tests/test_playground.py \
  tests/test_company_agent.py
```

结果：

- `43 passed`

另外此前也单独跑过：

- `tests/test_company_agent.py`
- `tests/test_agent_company_integration.py`

## 重要实现细节

### 1. 主 agent handoff 一律要求用户确认

这是当前实现里最重要的产品约束：

- 独立 `company-agent` 允许自己 `resolved`
- 但接入主 agent 时会统一转成 `need_select`

这样前端总能用列表或单项确认卡承接，不会绕过人工确认。

### 2. 用户继续输入时，不走普通聊天确认

前端卡片里的继续输入不会发到 `/chat`，而是走：

- `/api/agent/distributors/company/search`

这样避免：

- 输入“上海码岱码网络科技”
- 被主 agent 当成普通聊天文本继续抽取

而是直接用于启信宝实时查询候选。

### 3. 确认提交后才写 `distributorName`

只有调用：

- `/api/agent/distributors/company/commit`

才会把最终名称写入：

- `main_info.distributorName`

## 当前已知问题 / 风险

### 1. `company-agent` 的候选排序仍然不够稳

比如：

- `上海码代码网络科技`

这类错字 / 同音字输入，当前 live 行为可能仍会返回多个候选，需要人工挑选。

也就是说：

- 集成链路已经通
- 但识别准确率和排序还可以继续优化

### 2. 当前 worktree 里还有很多非本任务改动

`git status` 显示 `.worktrees/location-agent` 里还有很多已有修改，不全是本次经销商名称接入引入的，包括：

- `app/location_agent/*`
- `app/agent/dialog_policy.py`
- `tests/test_location_agent.py`
- 其他文档和测试

下次继续时不要假设整个 worktree 只有本次改动。

### 3. 主流程里 `distributorName` 仍然经过 mock validation

`app/agent/validators.py` 里的 `validate_distributor_name()` 还是 mock 逻辑：

- 长度校验
- 黑名单校验

目前没和 `company-agent` 的工商校验结果联动。

现状是：

- 先用 `company-agent` 做公司名称确认
- 再把结果写到主状态
- 主状态层仍会跑一次 mock validation

这不会挡住当前流程，但长期看需要统一。

## 下次如果继续，优先建议

### 1. 优化 `company-agent` 排序

优先改：

- `app/company_agent/prompts.py`
- `app/company_agent/service.py`

方向：

- 提升 `discover_candidates_from_web_search()` 的约束
- 缩小“语义相关但字面差很远”的候选
- 提高启信宝验真后候选的排序质量

### 2. 主流程里展示更明确的候选理由

前端目前只是下拉展示公司名。

可以继续补：

- `match_reason`
- `source`
- `match_confidence`

让用户更容易选。

### 3. 考虑把主 flow 的 `company/search` 支持更丰富的候选信息

现在实时输入卡片只需要公司名。

后面可考虑展示：

- 法人
- 成立日期
- 信用代码

这些启信宝原始字段已经在 `/api/qixin/companies/search` 里有。

## 快速复现命令

### 启动 / 重启环境

```bash
cd /Users/ganzhiwen/workspace/InformationEntryAgent/.worktrees/location-agent
docker compose -f docker-compose.location-agent.yml up -d --force-recreate app
```

### 跑核心测试

```bash
docker compose -f docker-compose.location-agent.yml exec app python -m pytest \
  tests/test_agent_company_integration.py \
  tests/test_api_chat.py \
  tests/test_playground.py \
  tests/test_company_agent.py
```

### 打开联调页

```text
http://127.0.0.1:8010/playground/distributor-agent
```

### 主 agent 触发公司名称确认

```bash
curl -X POST http://127.0.0.1:8010/api/agent/distributors/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"debug-company-1","message":"新增经销商，经销商叫契胜，客户手机号13800138000。"}'
```

### 公司名称实时搜索

```bash
curl -X POST http://127.0.0.1:8010/api/agent/distributors/company/search \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"debug-company-1","keyword":"上海码岱码网络科技"}'
```

## 一句话结论

当前 `.worktrees/location-agent` 已经完成：

- 主 agent 识别 `distributorName`
- 切入公司名称子流程
- 调用 `company-agent`
- 前端下拉候选确认
- 手动输入实时启信宝搜索
- 确认后回写主状态

链路已通，下一步主要是继续优化公司候选排序和识别准确率。
