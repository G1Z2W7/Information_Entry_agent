# 新增经销商 Agent 混合输入实现方案

## 1. 文档目标

本文档定义“新增经销商 Agent”的下一阶段实现方案：在保持同一会话状态不变的前提下，将用户输入拆分为两类来源：

- 前端结构化输入
- 自然语言输入

目标是降低枚举字段的归一化压力，让枚举值直接由前端以标准值采集；同时保留自然语言录入能力，继续由 LLM 处理名称、联系人、地址、备注等自由文本信息。

本文档是对现有设计的增量扩展，基础状态机、必填规则、多轮会话逻辑仍然沿用现有方案。

## 2. 背景与问题

当前流程中，所有字段原则上都由自然语言进入 `chat` 接口，再由 LLM 增量提取。

这种方式已经可以工作，但在以下字段上稳定性不足：

- `mainCategory`
- `mainCategoryGrade`
- `businessType`
- `cooperationStatus`
- `status`
- `informationSource`
- 其他存在明确标准值域的字段

评测结果表明，当前主要误差不是“完全提不出来”，而是“提到了语义，但没有归一化成系统标准值”。

因此，下一阶段应将“有明确枚举值域的字段”前移到前端，让用户直接选择标准值。

## 3. 总体方案

### 3.1 核心原则

- 仍然只维护一份会话状态
- 同一个 `session_id` 同时接收两类输入
- 两类输入最终都 merge 到同一个 `SessionState`
- 后端仍然统一负责缺失字段判断、校验、确认创建和提交

### 3.2 输入分层

输入分为两类：

1. 结构化输入
2. 自然语言输入

结构化输入适用于：

- 枚举字段
- 布尔字段
- 日期字段
- 少量适合控件输入的数字字段

自然语言输入适用于：

- 企业名称
- 上级经销商名称
- 联系人信息
- 地址信息
- 关系描述
- 备注信息
- 其他难以通过控件完整表达的信息

### 3.3 会话模型不变

无论用户通过哪种方式输入，后端都使用同一个 `session_id` 读取和更新同一个会话状态。

即：

- 前端下拉选择 `main_info.mainCategory=汽配`
- 自然语言输入“联系人王磊，电话 13900001111”

这两类数据都进入同一个 `SessionState`，而不是两个平行流程。

## 4. 字段分层建议

### 4.1 优先改为前端结构化输入的字段

建议第一批前端化的字段：

- `main_info.mainCategory`
- `main_info.mainCategoryGrade`
- `main_info.businessType`
- `main_info.cooperationStatus`
- `main_info.status`
- `main_info.informationSource`
- `main_info.providePoints`

第二批可继续前端化的字段：

- `main_info.ownBrandDisplay`
- `main_info.competitorBrandDisplay`
- `sites[0].siteType`
- `sites[0].storeAreaRange`

第三批可选前端化字段：

- `main_info.issueDate`
- `main_info.expiryDate`
- `main_info.providePointsRatio`

### 4.2 继续保留自然语言抽取的字段

- `main_info.distributorName`
- `main_info.parentDistributorName`
- `main_info.customerEmail`
- `main_info.customerMobile`
- `main_info.salesUserName`
- `main_info.salesManagerName`
- `main_info.authorizedRegion`
- `main_info.belongRegion`
- `main_info.source`
- `main_info.erpCode`
- `main_info.discount`
- `contacts[*].contactName`
- `contacts[*].position`
- `contacts[*].mobile`
- `contacts[*].wechat`
- `contacts[*].remark`
- `sites[*].fullAddress`
- `sites[*].provinceName`
- `sites[*].cityName`
- `sites[*].districtName`
- `main_info.remark`

### 4.3 混合来源字段

以下字段允许同时由前端输入和自然语言输入：

- `main_info.issueDate`
- `main_info.expiryDate`
- `main_info.discount`
- `main_info.salesUserName`
- `main_info.salesManagerName`

处理原则：

- 前端结构化输入优先使用标准值
- 自然语言输入仍可作为补充来源
- 后端统一 merge

## 5. 后端接口设计

### 5.1 保留现有 chat 接口

现有接口继续保留：

- `POST /api/agent/distributors/chat`

职责：

- 处理自然语言输入
- 调用 LLM 提取自由文本字段
- merge 到当前会话状态
- 返回当前阶段、缺失字段、校验结果、创建结果

### 5.2 新增结构化字段提交接口

建议新增：

- `PATCH /api/agent/distributors/fields`

职责：

- 接收前端直接提交的结构化字段 patch
- 不走 LLM
- 直接 merge 到当前会话状态
- 统一刷新缺失字段、校验状态、阶段
- 返回与 `chat` 接口同结构的响应

### 5.3 请求结构建议

请求体建议为：

```json
{
  "session_id": "web-xxx",
  "patch": {
    "main_info": {
      "mainCategory": "汽配",
      "mainCategoryGrade": "国内主流品牌为主",
      "businessType": "批发B2B",
      "cooperationStatus": "稳定合作｜已签约",
      "status": "normal",
      "providePoints": true
    }
  }
}
```

说明：

- `patch` 结构直接复用当前内部 merge 结构
- 这样可以最大程度复用已有 `merge_state` 逻辑

### 5.4 响应结构建议

响应建议继续复用现有 `ChatResponse` 或抽象出通用 `SessionResponse`：

```json
{
  "session_id": "web-xxx",
  "reply": "已更新主营品类、主营品类档次、经营类型。",
  "stage": "collecting",
  "missing_required_fields": [],
  "validation_results": {},
  "state_summary": {},
  "created_result": null
}
```

说明：

- `fields` 接口也应返回统一响应结构，便于前端共用渲染逻辑
- `reply` 可以是简短确认文本，也可以为空

## 6. 后端模块改造

### 6.1 新增字段提交请求模型

建议新增模型：

- `StructuredPatchRequest`

字段：

- `session_id`
- `patch`

位置建议：

- `app/agent/models.py`

### 6.2 新增结构化 patch 处理入口

建议在 `AgentService` 中新增方法：

- `process_structured_patch(session_id: str, patch: dict[str, Any]) -> ChatResponse`

职责：

- 读取会话状态
- merge 结构化 patch
- 对变更字段触发校验
- 调用 `decide_next_action`
- 返回统一响应

### 6.3 共用状态刷新逻辑

`process_chat()` 与 `process_structured_patch()` 都应复用统一的后处理逻辑，例如：

- merge
- validate changed fields
- refresh state flags
- decide next action
- render reply
- save state

建议抽一个内部公共方法，避免双入口后出现行为漂移。

### 6.4 枚举值后端兜底校验

虽然枚举值来自前端，但后端仍必须校验是否落在允许值域中。

原因：

- 前端不能作为可信边界
- 防止非法值直接写入状态
- 防止未来多端接入时标准不一致

建议：

- 新增统一枚举常量定义
- `StructuredPatchRequest` 入参校验时做一次约束
- merge 前再次做字段级兜底校验

## 7. 枚举定义管理

### 7.1 统一枚举源

建议新增统一常量模块，例如：

- `app/agent/enums.py`

内容包括：

- `MAIN_CATEGORY_OPTIONS`
- `MAIN_CATEGORY_GRADE_OPTIONS`
- `BUSINESS_TYPE_OPTIONS`
- `COOPERATION_STATUS_OPTIONS`
- `STATUS_OPTIONS`
- `INFORMATION_SOURCE_OPTIONS`

### 7.2 前后端共享原则

前后端必须使用同一份标准值集合。

V1 可接受做法：

- 后端维护常量
- 前端先静态复制

更稳妥做法：

- 后端新增枚举元数据接口
- 前端启动时拉取

建议接口：

- `GET /api/agent/distributors/field-options`

返回：

```json
{
  "main_info.mainCategory": ["五金工具", "设备 & 机床", "汽配", "其他"],
  "main_info.mainCategoryGrade": ["国际品牌为主", "国内主流品牌为主", "国内非主流品牌为主", "无法判断"],
  "main_info.businessType": ["零售B2C", "贸易B2F", "批发B2B", "综合类均有"],
  "main_info.cooperationStatus": ["稳定合作｜已签约", "已供货｜未签约", "已接触｜待跟进", "未合作｜仅线索"],
  "main_info.status": ["normal", "disabled"]
}
```

## 8. 前端改造方案

### 8.1 现状

当前联调页已经存在简易 `quick-fill` 区域，且已支持：

- `mainCategory`
- `mainCategoryGrade`

这说明现有前端结构已经适合继续扩展，而不是重做整页。

### 8.2 第一阶段前端改造

在现有 `quick-fill` 面板基础上继续扩展下拉或单选控件：

- 主营品类
- 主营品类档次
- 经营类型
- 合作状态
- 经销商状态
- 是否发积分
- 信息来源

展示逻辑：

- 当字段仍在 `missing_required_fields` 中时，优先展示
- 对非必填但推荐填写的枚举字段，可在扩展面板中展示

### 8.3 提交方式

前端不要再把下拉结果拼接成自然语言发给 `chat`。

建议改为：

- 自然语言输入框仍调 `/chat`
- 下拉选择提交调 `/fields`

这样可以避免：

- 标准值再次被 prompt 重写
- 结构化值在模型输出时被改写
- 前端明明拿到了标准值，最后仍被 LLM 干扰

### 8.4 前端状态

前端仍只维护一个 `sessionId`，不引入第二套会话状态。

建议前端本地只维护：

- 当前 `sessionId`
- 当前缺失字段
- 当前阶段
- 当前已选但未提交的结构化字段

服务端状态仍然是唯一事实来源。

## 8.5 地址双来源预留

考虑到当前业务发生在移动端，地址后续建议采用双来源：

1. 用户自然语言输入原始地址文本
2. 移动端在销售位于门店现场时提供当前位置

当前阶段先不接入真实定位服务，但后端应保留地址解析接口位置：

- `POST /api/agent/distributors/address/resolve`

预期后续能力：

- 输入 `full_address`
- 可选输入 `current_location`
- 由地址解析服务返回标准化地址、行政区划、经纬度

当前阶段实现要求：

- 保留请求/响应模型
- 保留 resolver 抽象
- 提供 placeholder 实现
- 不影响当前 LLM 文本抽取流程

## 9. 会话流转示例

### 9.1 示例流程

1. 新建会话 `session_id=web-001`
2. 用户输入：“新增一个经销商，名称叫智行汽车，联系人王磊，电话 13900001111”
3. 前端调用 `POST /chat`
4. 后端提取名称、联系人、电话并写入 `SessionState`
5. 后端返回缺失字段：`main_info.mainCategory`、`main_info.businessType`、`main_info.cooperationStatus`
6. 前端展示对应下拉
7. 用户选择：
   - 主营品类 = 汽配
   - 经营类型 = 批发B2B
   - 合作状态 = 稳定合作｜已签约
8. 前端调用 `PATCH /fields`
9. 后端将结构化 patch merge 到同一个 `session_id=web-001` 的状态
10. 后端继续返回剩余缺失字段或进入确认阶段

说明：

- 整个过程中没有第二个会话
- 两种输入方式只是两种写入入口

## 10. 实施步骤建议

### Step 1

新增后端统一枚举常量模块。

### Step 2

新增 `PATCH /fields` 接口和请求模型。

### Step 3

在 `AgentService` 中新增 `process_structured_patch()`。

### Step 4

重构公共状态更新逻辑，避免 `chat` 和 `fields` 两条入口行为不一致。

### Step 5

前端把现有 `quick-fill` 从“拼自然语言”改为“直接提交结构化 patch”。

### Step 6

扩展更多枚举字段的下拉控件。

### Step 7

补测试：

- 结构化 patch merge 测试
- 非法枚举值校验测试
- 同一会话下 chat + fields 混合输入测试
- 前端联调测试

## 11. 测试建议

### 11.1 单元测试

- `tests/test_models.py`
  - `StructuredPatchRequest` 合法与非法值校验

- `tests/test_state_merge.py`
  - 结构化 patch 正确 merge 到状态

- `tests/test_dialog_policy.py`
  - 结构化字段补全后缺失字段减少

- `tests/test_api_chat.py`
  - 新增 `PATCH /fields` 接口测试

### 11.2 集成测试

增加混合输入场景：

1. 先通过 `chat` 输入自然语言
2. 再通过 `fields` 补枚举字段
3. 检查同一个 `session_id` 下状态是否完整
4. 检查是否能进入 `AWAITING_CONFIRMATION`

### 11.3 回归评测

在 `evals/` 中新增对照评测：

- 纯自然语言模式
- 混合输入模式

对比以下指标：

- 必填字段召回率
- 枚举字段准确率
- exact match rate
- 平均交互轮数

## 12. 预期收益

引入混合输入后，预期收益包括：

- 枚举字段准确率显著提高
- LLM prompt 负担下降
- 多轮补全流程更稳定
- 真实创建接口入参质量更高
- 前端引导能力更强

## 13. 非目标

本阶段不处理以下事项：

- 不重做整套前端页面
- 不把所有字段都改成表单式录入
- 不引入复杂前端状态管理框架
- 不取消自然语言输入能力
- 不改变现有单会话状态模型

## 14. 结论

下一阶段的正确方向不是“继续把所有字段都交给 LLM 归一化”，而是建立：

- 前端负责标准枚举值采集
- LLM 负责自由文本理解
- 后端负责统一状态合并与流程控制

这是一种“同一会话、双入口写入、单状态汇总”的混合输入方案，适合作为当前经销商 Agent 的下一阶段实现路径。
