# 新增经销商 Agent 设计文档

## 1. 目标

本文档定义“新增经销商信息维护”场景下的 Agent 设计方案。

当前目标不是构建一个开放式通用 Agent，而是实现一个面向单一业务流程的多轮字段收集 Agent，用于通过自然语言对话完成经销商新增前的信息采集、校验、确认和提交。

Agent 的职责：

- 通过多轮对话从用户自然语言中收集字段
- 持续维护当前会话中的结构化状态
- 对关键字段执行校验
- 判断哪些必填字段缺失
- 在字段完整且校验通过后展示汇总结果
- 等待用户确认后调用新增经销商接口

非目标：

- 不做开放式任务规划
- 不做跨业务场景泛化
- V1 不做跨会话长期业务记忆回填
- V1 不直接依赖真实后端接口，先使用 mock 校验适配器

## 2. 业务流程

整体流程如下：

1. 前端创建会话
2. 用户通过 chat 与 Agent 多轮对话
3. Agent 从每轮输入中增量提取字段并合并到会话状态
4. Agent 对名称、手机号、邮箱执行校验
5. Agent 根据当前状态判断仍缺失的必填字段
6. Agent 继续追问，直到必填字段齐全且校验通过
7. Agent 展示结构化汇总，询问用户是否补充或修改
8. 用户确认后，Agent 调用新增经销商接口
9. 创建成功后返回结果并结束流程

## 3. 业务规则

### 3.1 主信息必填字段

- `distributorName`
- `distributorLevel`
- `customerEmail`
- `customerMobile`
- `belongRegion`
- `erpCode`
- `status`
- `providePoints`
- `providePointsRatio`
- `mainCategory`
- `mainCategoryGrade`
- `businessType`
- `cooperationStatus`

### 3.2 条件必填字段

- 当 `distributorLevel == 2` 时，`parentDistributorName` 必填

### 3.3 联系人规则

- 至少需要 1 个联系人
- 至少存在 1 个有效联系人
- 有效联系人需包含以下字段：
  - `contactName`
  - `position`
  - `mobile`
  - `wechat`
- 若存在多个联系人且用户未明确指定主联系人，则默认第一个联系人为主联系人

### 3.4 场地规则

- 场地为非必填

### 3.5 默认值规则

- `distributorLevel` 默认值为 `1`
- 当 `providePoints == false` 时，`providePointsRatio` 归一为 `0`

### 3.6 枚举规则

- `status` 只允许：
  - `normal`
  - `disabled`

### 3.7 校验规则

以下字段必须校验通过，否则不能进入创建阶段：

- `distributorName`
- `customerMobile`
- `customerEmail`

名称校验失败时必须拦截，不能创建。

## 4. 当前字段范围

字段结构沿用现有约定：

- `main_info`
- `contacts[]`
- `sites[]`

字段定义来源于仓库中的 [字段.md](/Users/ganzhiwen/workspace/InformationEntryAgent/字段.md)。

V1 重点围绕新增经销商必需字段，不要求一次覆盖文档中的全部扩展字段能力，但数据结构设计需兼容后续扩展。

## 5. 设计原则

### 5.1 状态机优先

本方案采用“状态机 + 增量抽取 + 字段校验”的实现方式，而不是完全依赖模型自主规划。

原因：

- 业务流程固定
- 必填规则明确
- 校验逻辑刚性强
- 对结果可靠性要求高
- 需要可解释、可调试、可扩展

### 5.2 增量抽取

Agent 每轮只处理“本轮用户输入”，不重复对整段历史对话做全量抽取。

原因：

- 当前单轮全量抽取耗时约 10 到 15 秒，不能直接用于高频多轮对话
- 多轮累计后重复抽取成本高
- 已确认字段不需要被频繁重算

### 5.3 规则优先，LLM 兜底

简单、稳定、格式清晰的字段优先用规则提取：

- 手机号
- 邮箱
- ERP 编码
- 日期
- 折扣
- 布尔值
- “微信同手机号”

复杂语义字段使用 LLM 抽取和归一化：

- 主营品类
- 主营品类档次
- 经营类型
- 合作状态
- 联系人关系
- 用户修改意图
- 场地类型语义归一

## 6. 技术选型

### 6.1 接口框架

接口层采用 `FastAPI`。

选择原因：

- 当前项目依赖中已经包含 `fastapi` 和 `uvicorn`
- 适合快速提供 chat 类 HTTP 接口
- 与 `Pydantic` 集成紧密，便于定义请求、响应和状态模型
- 后续接前端会话接口和后端校验接口都比较直接

### 6.2 数据模型

数据模型采用 `Pydantic`。

主要用于：

- 会话状态建模
- 主信息、联系人、场地结构建模
- 校验结果建模
- API 请求和响应结构建模

### 6.3 LLM 调用层

LLM 调用层采用：

- `LangChain`
- `langchain-openai`

使用方式限定为：

- Prompt 组织
- 模型调用封装
- 结构化输出适配

不将业务流程控制交给 LangChain Agent。

### 6.4 流程编排

流程编排采用自定义 Python 状态机，不使用 `LangGraph` 作为 V1 主编排框架。

选择原因：

- 当前业务流程固定
- 阶段流转明确
- 必填规则和校验规则刚性强
- 自定义状态机更容易调试、测试和维护

`LangGraph` 后续如需扩展复杂工作流可再评估，但不作为 V1 必需组件。

### 6.5 会话状态存储

短期会话状态建议采用 `Redis`。

主要用途：

- 存储当前会话的结构化字段状态
- 存储当前阶段和追问上下文
- 支持多轮对话连续性
- 支持服务实例横向扩展

在本地开发或早期联调阶段，也可先提供内存版状态存储实现，后续再切换到 Redis。

### 6.6 后端接口调用

外部接口调用采用 `httpx`。

主要用于后续接入：

- 经销商名称校验接口
- 手机号校验接口
- 邮箱校验接口
- 新增经销商接口

V1 在真实接口未接入前，先提供 mock adapter。

### 6.7 字段抽取策略

字段抽取采用“规则提取 + LLM 增量抽取”的混合方案。

- 规则提取负责稳定格式字段
- LLM 负责复杂语义字段和修改意图识别
- 每轮只对本轮用户输入做抽取

### 6.8 测试框架

测试采用：

- `pytest`
- `pytest-asyncio`

重点测试内容：

- 必填字段判断
- 会话状态 merge
- 修改意图覆盖
- 状态机流转
- mock 校验逻辑
- 汇总确认条件

### 6.9 推荐技术组合

V1 推荐组合如下：

- `FastAPI`：提供 chat 服务接口
- `Pydantic`：定义数据模型
- `LangChain + langchain-openai`：模型调用与 prompt 封装
- 自定义状态机：控制流程和阶段迁移
- `Redis`：短期会话状态存储
- `httpx`：调用后端接口
- `pytest`：测试

## 7. 会话状态设计

### 6.1 顶层状态结构

建议维护统一的会话状态对象：

```json
{
  "session_id": "string",
  "stage": "collecting",
  "main_info": {},
  "contacts": [],
  "sites": [],
  "validation_results": {},
  "missing_required_fields": [],
  "awaiting_confirmation": false,
  "creation_ready": false,
  "last_asked_fields": [],
  "turn_count": 0,
  "history_summary": "",
  "field_meta": {}
}
```

### 6.2 stage 定义

- `collecting`
  - 正在收集字段
- `validating`
  - 已收集到关键字段，正在或需要执行校验
- `awaiting_confirmation`
  - 必填字段完整且校验通过，等待用户确认
- `creating`
  - 用户确认后，准备调用创建接口
- `completed`
  - 已创建成功或流程结束

### 6.3 field_meta 建议

为每个字段保留元信息，便于后续做审计、调试和冲突处理：

```json
{
  "main_info.distributorName": {
    "source_turn": 2,
    "source_text": "新增一个二级经销商，名称叫智行汽车",
    "normalized_from": "智行汽车",
    "confidence": 0.93
  }
}
```

建议记录：

- 来源轮次
- 来源文本
- 归一化前原值
- 置信度
- 最近更新时间

## 8. 记忆设计

### 7.1 短期记忆

短期记忆指当前会话内可变信息，包含：

- 已收集结构化字段
- 最近若干轮对话
- 最近一次追问的字段
- 最近一次校验失败原因
- 当前阶段

短期记忆是 V1 的核心。

### 7.2 上下文记忆

给模型的上下文不直接拼接整段原始对话，而是构造成：

- 当前结构化状态摘要
- 缺失字段列表
- 最近 1 到 3 轮用户输入
- 本轮用户输入

这样可以减少 token 消耗并降低模型被无关历史干扰的概率。

### 7.3 长期记忆

V1 不启用跨会话业务记忆自动带入。

原因：

- 新增经销商场景对数据污染敏感
- 不同会话之间的信息复用风险高
- 业务上缺少明确的长期记忆边界

V1 只预留长期记忆接口，不做默认启用。

## 9. 抽取与归一化设计

### 8.1 抽取入口

每轮输入统一进入：

`extract_fields(message, state) -> extracted_patch`

输出 patch 只包含本轮识别出的新增或修改字段。

### 8.2 Patch 示例

```json
{
  "main_info": {
    "distributorName": "智行汽车",
    "customerMobile": "13800138000"
  },
  "contacts": [
    {
      "contactName": "王磊",
      "position": "老板",
      "mobile": "13900001111",
      "wechat": "same_as_mobile",
      "isPrimary": true
    }
  ]
}
```

### 8.3 归一化规则

建议统一做以下归一化：

- `七折` -> `0.7`
- `58折` -> `0.58`
- `正常` -> `normal`
- `禁用` -> `disabled`
- `发积分` -> `providePoints = true`
- `不发积分` -> `providePoints = false`
- `微信同手机号` -> `same_as_mobile`
- `2026年6月1日` -> `2026-06-01`

### 8.4 修改意图识别

用户常见表达包括：

- “手机号改成 138xxxx”
- “上级经销商不是这个”
- “邮箱换一下”
- “主联系人改成刘芳”

当识别到修改意图时，应覆盖已有字段，而不是追加重复值。

## 10. Merge 策略

### 9.1 主信息

`main_info` 使用字段级覆盖策略：

- 本轮未提及的字段保持不变
- 本轮明确修改的字段直接覆盖
- 本轮提到空值删除时，需要记录用户意图并清空对应字段

### 9.2 联系人

联系人合并建议按“语义匹配优先”的方式处理：

- 若能根据 `contactName` 匹配到现有联系人，则更新该联系人
- 若无姓名但职位明确且足以唯一定位，可尝试按职位匹配
- 若无法匹配，则新增联系人

### 9.3 场地

场地虽然非必填，但结构上保持同样的 patch merge 机制：

- 按 `siteType + fullAddress` 优先匹配
- 匹配失败则新增

## 11. 校验设计

### 10.1 校验抽象

定义统一校验服务：

```python
class ValidationService:
    def validate_distributor_name(self, name: str) -> ValidationResult: ...
    def validate_mobile(self, mobile: str) -> ValidationResult: ...
    def validate_email(self, email: str) -> ValidationResult: ...
```

### 10.2 V1 mock 策略

在未接入真实接口前，使用 mock 校验：

- 名称：非空且长度合理时默认通过；可预留特定名称触发失败
- 手机：满足常见手机号格式时通过
- 邮箱：满足常见邮箱格式时通过

### 10.3 校验结果结构

```json
{
  "main_info.distributorName": {
    "valid": true,
    "code": "OK",
    "message": "validated by mock"
  }
}
```

建议结果字段：

- `valid`
- `code`
- `message`
- `raw_response`
- `validated_at`

### 10.4 校验触发时机

以下情况应重新校验：

- 首次提取到 `distributorName`
- 首次提取到 `customerMobile`
- 首次提取到 `customerEmail`
- 用户修改了上述任一字段

## 12. 缺失必填字段判断

定义统一函数：

`compute_missing_fields(state) -> list[str]`

判断逻辑包含：

- 主信息必填字段缺失
- 条件必填字段缺失
- 联系人是否存在
- 联系人必填子字段是否完整
- 校验失败字段是否阻塞

建议将缺失字段分为两类：

- `hard_missing`
  - 未提供
- `hard_invalid`
  - 已提供但校验失败或枚举非法

这样回复用户时更清晰。

## 13. 对话策略设计

### 12.1 回复目标

每轮回复只做一件主要事情：

- 追问缺失字段
- 说明校验失败
- 展示汇总等待确认
- 确认创建结果

避免一轮消息里同时塞入过多信息。

### 12.2 追问原则

- 每轮最多追问 1 到 2 个关键字段
- 优先追问阻塞创建的字段
- 优先追问用户最容易直接回答的字段
- 不追问非必填字段
- 对 `salesUserName`、`salesManagerName` 不主动追问

### 12.3 汇总确认

当满足以下条件时进入 `awaiting_confirmation`：

- 所有必填字段已满足
- 所有强校验字段已通过
- 联系人要求已满足

此时 Agent 展示：

- 已收集主信息摘要
- 联系人摘要
- 可选的场地摘要
- 是否还有补充或修改
- 是否确认创建

### 12.4 创建前再修改

若用户在确认阶段提出变更：

- 更新状态
- 对受影响字段重新校验
- 重新计算缺失字段
- 必要时退出 `awaiting_confirmation` 回到 `collecting`

## 14. 对外接口抽象

建议拆分以下内部能力：

### 13.1 抽取

`extract_fields(message, state) -> extracted_patch`

### 13.2 合并

`merge_state(state, patch) -> state`

### 13.3 校验

`validate_fields(state, changed_paths) -> validation_results`

### 13.4 缺失判断

`compute_missing_fields(state) -> missing_result`

### 13.5 决策

`decide_next_action(state) -> action`

### 13.6 文本渲染

`render_reply(state, action) -> str`

### 13.7 创建

`create_distributor(state) -> create_result`

## 15. 推荐目录结构

建议在后续实现时采用如下目录：

```text
app/
  agent/
    models.py
    state.py
    extractor.py
    normalizers.py
    validators.py
    dialog_policy.py
    service.py
    prompts.py
  api/
    chat.py
```

职责建议：

- `models.py`
  - Pydantic 数据模型
- `state.py`
  - 状态对象与状态迁移辅助方法
- `extractor.py`
  - 规则抽取与 LLM 抽取编排
- `normalizers.py`
  - 枚举与格式归一化
- `validators.py`
  - mock 校验器与后续真实接口适配器
- `dialog_policy.py`
  - 缺失字段判断与下一步动作决策
- `service.py`
  - chat 主流程编排
- `prompts.py`
  - LLM 提示词模板

## 16. 处理链路示意

```text
用户输入
  -> 增量字段抽取
  -> 字段归一化
  -> patch merge 到会话状态
  -> 触发关键字段校验
  -> 重新计算缺失必填和非法字段
  -> 决定下一步动作
  -> 渲染回复文本
  -> 返回前端
```

## 17. 性能优化方向

当前单轮全量字段抽取约 10 到 15 秒，V1 需要重点优化交互时延。

建议策略：

- 每轮只抽本轮输入
- 规则抽取前置，减少 LLM 工作量
- 按字段组触发抽取，而非每次全字段全量抽取
- 对稳定字段避免重复校验
- 后续如接真实后端接口，可将独立校验并行执行

目标是将普通一轮对话处理时间压缩到可交互范围。

## 18. 风险与注意事项

### 17.1 联系人 merge 风险

若用户只说“采购电话改一下”，但存在多个采购角色，可能出现错误覆盖。

处理建议：

- 匹配不唯一时主动澄清
- 不做高风险覆盖

### 17.2 修改意图识别风险

用户表达中“不是”“换成”“还是用之前那个”都属于修改型意图，需重点覆盖。

### 17.3 长期记忆污染风险

跨会话记忆在新增经销商场景下容易引入旧数据，不应在 V1 启用。

### 17.4 枚举无后端字典风险

当前 `mainCategory`、`businessType`、`cooperationStatus` 等暂时没有后端标准字典，V1 需在本地维护归一化映射，后续再替换。

## 19. 实施顺序

建议按以下顺序开发：

1. 定义数据模型和会话状态模型
2. 实现必填规则与状态机
3. 实现增量抽取与 patch merge
4. 实现 mock 校验服务
5. 实现缺失字段判断和对话决策
6. 实现汇总确认逻辑
7. 最后接入真实后端接口

## 20. V1 交付范围

V1 需要完成：

- 多轮会话状态维护
- 必填字段增量收集
- 联系人必填逻辑
- mock 名称/邮箱/手机号校验
- 缺失字段追问
- 汇总确认
- 创建前拦截逻辑

V1 暂不包含：

- 跨会话长期记忆
- 全量真实后端对接
- 全字段字典服务
- 草稿保存

## 21. 结论

本方案适合当前业务目标：先把“新增经销商”这个单场景流程跑通，强调稳定性、确定性和后续可接后端的工程结构。

后续实现阶段应坚持以下原则：

- 流程控制交给代码
- 语义理解交给模型
- 字段可靠性交给校验
- 会话连续性交给状态管理
