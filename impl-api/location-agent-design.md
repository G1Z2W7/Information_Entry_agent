# 位置解析 Agent 设计方案

## 1. 文档目标

本文档定义“位置解析 Agent”的职责边界、交互状态、工具依赖和返回协议。

目标是为现有字段提取 Agent 增加一条独立的位置处理链路：当主 Agent 识别到用户输入涉及位置时，将位置相关输入转交给位置解析 Agent；位置解析 Agent 负责位置理解、候选收敛、用户选择、手工录入兜底，并最终返回标准化的位置字段。

最终返回目标为：

- `provinceName`
- `cityName`
- `districtName`
- `detailAddress`
- `fullAddress`

如可获得，也返回：

- `formattedAddress`
- `latitude`
- `longitude`
- `geoSource`
- `confidence`

## 2. 业务定位

位置解析 Agent 不是一个单纯的“地址字符串转结构化字段”的工具函数，而是一个带多轮交互状态的小型状态机。

主 Agent 的职责缩减为：

- 识别本轮是否涉及位置
- 将用户原话、用户选择结果和位置子状态转交给位置解析 Agent
- 在位置解析 Agent 返回 `resolved` 时回填最终地址字段

位置解析 Agent 自身负责：

- 判断用户是否已输入位置
- 调用当前位置和地图检索工具
- 调用 DeepSeek 做位置语义理解、纠错和检索词扩展
- 在不确定时返回候选列表让用户选择
- 在地址过于模糊时追问缺失细节
- 在地图无法命中但用户坚持地址有效时，支持人工确认落库

## 3. 设计原则

### 3.1 地图服务是标准化事实源

高德返回的候选地址、行政区和坐标优先作为标准化结果来源。

### 3.2 LLM 负责理解，不负责拍板最终地址

DeepSeek 负责：

- 提取原始地址片段
- 判断输入属于精确地址、模糊地址还是不可识别
- 纠正明显错别字
- 生成多个检索 query
- 识别还缺哪些位置信息

DeepSeek 不直接生成最终标准地址作为事实结果。

### 3.3 用户确认是最终兜底

当地图未命中但用户确认地址真实有效时，允许按“用户确认地址”保存结果，并标记来源。

### 3.4 当前位置只作为快捷候选来源

当用户未输入位置时，可以根据当前位置给出附近候选，但不能默认把当前位置当成最终录入地址。

## 4. 工具依赖

位置解析 Agent 依赖以下 3 类工具。

### 4.1 获取当前经纬度

- `get_current_coordinates()`

职责：

- 获取用户当前位置经纬度
- 当前阶段先用 mock 实现

### 4.2 基于经纬度获取附近位置列表

- `amap_nearby_candidates(lat, lng)`

职责：

- 根据当前位置查询附近 POI / 地址候选
- 用于“用户未输入位置”的快捷选择场景

### 4.3 基于文本检索地址候选

- `amap_search_by_text(query, city_hint?)`

职责：

- 根据用户输入的地址文本、地标、园区、市场、路名、门牌等进行候选检索
- 支撑“用户已输入位置”的主链路

## 5. Agent 输入与输出边界

### 5.1 主 Agent 传入内容

建议主 Agent 每次调用位置解析 Agent 时传入：

- `session_id`
- `user_message`
- `location_state`
- `selection_payload`
  - 当用户本轮是在选候选项时传入
- `manual_input_payload`
  - 当用户本轮是在手工录入或确认地址时传入

### 5.2 位置解析 Agent 返回状态

位置解析 Agent 返回以下 4 类主状态之一：

- `resolved`
- `need_select`
- `need_more_detail`
- `need_manual_input`

语义如下：

- `resolved`
  - 已确定最终标准地址，可直接回填
- `need_select`
  - 已有 1 组或多组候选地址，需要用户选择
- `need_more_detail`
  - 位置太模糊，需补充更细信息
- `need_manual_input`
  - 当前无法可靠解析，进入手工录入或人工确认流程

### 5.3 推荐返回结构

```json
{
  "status": "resolved",
  "message": "location resolved",
  "suggested_reply": "已识别到地址：浙江省杭州市西湖区文三路18号，请确认。",
  "candidates": [],
  "resolved_address": {
    "provinceName": "浙江省",
    "cityName": "杭州市",
    "districtName": "西湖区",
    "detailAddress": "文三路18号",
    "fullAddress": "浙江省杭州市西湖区文三路18号",
    "formattedAddress": "浙江省杭州市西湖区文三路18号",
    "latitude": 30.2741,
    "longitude": 120.1551,
    "geoSource": "map_precise",
    "confidence": "high"
  },
  "state": {}
}
```

说明：

- `message` 面向主 Agent 或日志
- `suggested_reply` 是位置 Agent 推荐给用户展示的话术，主 Agent 可直接透传，也可按需改写
- `state` 用于保存位置子状态，供下一轮继续处理

## 6. 状态机设计

建议位置解析 Agent 内部维护以下子状态：

- `idle`
- `awaiting_nearby_selection`
- `awaiting_search_selection`
- `awaiting_more_detail`
- `awaiting_manual_input`
- `awaiting_user_confirmation`
- `resolved`

状态语义：

- `idle`
  - 尚未开始位置解析
- `awaiting_nearby_selection`
  - 已给出当前位置附近候选，等待用户选择
- `awaiting_search_selection`
  - 已给出文本检索候选，等待用户选择
- `awaiting_more_detail`
  - 已识别到位置意图，但仍缺路名、门牌、楼栋、园区或市场等细节
- `awaiting_manual_input`
  - 地图和语义理解都无法稳定收敛，等待用户按模板手工输入
- `awaiting_user_confirmation`
  - 地图未完全命中，但已形成“用户确认版地址”，等待最终确认
- `resolved`
  - 已形成最终结构化地址

## 7. 主流程设计

### 7.1 用户未输入位置

触发条件：

- 主 Agent 识别到当前需要补位置
- 用户本轮没有提供任何有效位置文本

处理流程：

1. 调用 `get_current_coordinates()`
2. 调用 `amap_nearby_candidates(lat, lng)`
3. 返回附近位置列表供用户选择
4. 同时提供两个固定入口：
   - `不在当前位置`
   - `手工输入地址`

预期返回状态：

- `need_select`

注意事项：

- 附近候选只能作为快捷入口
- 不能把当前位置默认回填为录入地址
- 用户当前可能不在实际录入地点

### 7.2 用户输入了较完整地址

示例：

- “浙江省杭州市西湖区文三路18号”
- “上海市浦东新区张江路88号”

处理流程：

1. DeepSeek 提取原始地址片段
2. DeepSeek 判断为 `precise`
3. 使用原始地址直接调用 `amap_search_by_text`
4. 若唯一高置信命中，则直接返回最终地址
5. 若命中多个相近结果，则返回候选让用户选择

预期返回状态：

- 唯一命中：`resolved`
- 多个相近候选：`need_select`

### 7.3 用户输入地址存在错别字

示例：

- “杭洲市西胡区文三路”
- “苏洲工业园区星胡街”

处理流程：

1. DeepSeek 识别明显错别字和近音字
2. DeepSeek 生成多个纠错 query
3. 分别调用 `amap_search_by_text`
4. 汇总高相关候选
5. 若不能唯一确定，则返回候选让用户选择

处理原则：

- 可以纠错，但不能静默替用户拍板
- 当存在多个合理候选时，必须要求用户选择

### 7.4 用户输入位置很模糊

示例：

- “杭州西湖边那个店”
- “苏州园区那边门店”
- “在市场里面的办公点”

处理流程：

1. DeepSeek 提取可用位置线索：
   - 城市
   - 区县
   - 地标
   - 园区
   - 市场名
2. 基于线索调用 `amap_search_by_text`
3. 若候选范围过大，则进入追问
4. 明确提示用户补以下信息之一：
   - 路名
   - 门牌号
   - 楼栋号
   - 商场/园区/市场名

预期返回状态：

- `need_more_detail`

处理原则：

- 不要泛泛提示“请补充详细地址”
- 要根据缺失项给定明确补充方向

### 7.5 用户输入位置完全识别不出来

示例：

- 只有零碎 ASR 词片段
- 地址和非地址信息混杂且无法抽出稳定地点

处理流程：

1. DeepSeek 判断为 `unknown`
2. 不直接硬搜
3. 返回手工录入引导或更结构化的补充模板

推荐模板：

- `省/市/区（县） + 路/街道 + 门牌/园区/市场/楼栋`

预期返回状态：

- `need_manual_input`
  或
- `need_more_detail`

## 8. 地图未命中但地址真实存在时的兜底

这是位置解析 Agent 的关键兜底链路。

### 8.1 场景定义

用户输入的地址在现实中存在，但高德文本检索无法准确命中。例如：

- 新建园区
- 村镇道路
- 商户俗称
- 非标准门牌写法
- 地图收录滞后

### 8.2 兜底策略

当地图无法命中时，按以下顺序处理：

1. 尽量先确定 `provinceName / cityName / districtName`
2. 保留用户原始详细地址文本
3. 告知用户：
   - 地图未找到完全匹配地址
   - 可按用户确认地址保存
4. 用户确认后，返回人工确认地址

### 8.3 最终返回要求

此时仍可返回 `resolved`，但应明确标记：

- `geoSource = user_confirmed`
- `confidence = low` 或 `medium`

示例：

```json
{
  "provinceName": "江苏省",
  "cityName": "苏州市",
  "districtName": "吴中区",
  "detailAddress": "木渎镇金桥开发区5号仓旁边门面",
  "fullAddress": "江苏省苏州市吴中区木渎镇金桥开发区5号仓旁边门面",
  "formattedAddress": null,
  "latitude": null,
  "longitude": null,
  "geoSource": "user_confirmed",
  "confidence": "low"
}
```

这条策略可以避免地址录入流程卡死在长尾真实地址上。

## 9. DeepSeek 在位置 Agent 中的职责

DeepSeek 只负责“理解和收敛”，不负责“最终定址”。

建议输出字段包括：

- `raw_address_text`
- `address_type`
  - `precise`
  - `fuzzy`
  - `unknown`
- `corrected_queries`
- `admin_hints`
  - 省市区猜测
- `missing_parts`
  - 缺失路名、门牌、楼栋、市场名等
- `next_step`
  - 推荐下一步是检索、选候选、补细节还是手工录入

禁止行为：

- 凭语义猜一个完整标准地址直接落库
- 在存在多个合理候选时不经确认直接决定

## 10. 候选选择与文案原则

位置解析 Agent 除结构化结果外，还应返回推荐文案和候选项。

原因：

- 地址歧义说明属于位置语义范畴
- 候选展示和补充提示更适合由位置 Agent 统一生成
- 主 Agent 只需透传或轻度改写

文案原则：

- 明确说明为什么需要用户选择或补充
- 候选列表保持短，优先返回最相关的 3 到 5 个
- 始终提供“都不是 / 手工输入”入口

## 11. 最终标准字段建议

建议位置解析 Agent 最终返回以下字段：

- `provinceName`
- `cityName`
- `districtName`
- `detailAddress`
- `fullAddress`
- `formattedAddress`
- `latitude`
- `longitude`
- `geoSource`
- `confidence`

建议 `geoSource` 取值：

- `map_precise`
- `map_candidate_selected`
- `user_confirmed`

建议 `confidence` 取值：

- `high`
- `medium`
- `low`

## 12. 与主 Agent 的协作方式

主 Agent 不需要理解位置解析内部逻辑，只需要按以下模式集成：

1. 识别本轮是否涉及位置
2. 将用户原话和位置子状态交给位置解析 Agent
3. 若返回 `need_select / need_more_detail / need_manual_input`
   - 透传 `suggested_reply`
   - 渲染候选项或录入入口
4. 若返回 `resolved`
   - 将 `resolved_address` 回填到 `sites[*]` 对应字段

这样可以把位置处理能力与主字段采集流程解耦。

## 13. V1 实现建议

V1 先实现以下能力闭环：

1. 位置子状态模型
2. `get_current_coordinates()` mock
3. `amap_nearby_candidates(lat, lng)` 工具封装
4. `amap_search_by_text(query, city_hint?)` 工具封装
5. DeepSeek 位置预解析 prompt 和结构化输出
6. 候选选择、补充细节、手工录入 3 条交互分支
7. `user_confirmed` 兜底链路

V1 非目标：

- 不做复杂逆地理纠偏
- 不做多地址批量解析
- 不做地址知识库自建
- 不做自动坐标纠偏到门牌级精度

## 14. 结论

位置解析 Agent 的推荐方案为：

- `DeepSeek 预解析 + 高德检索标准化 + 用户确认收敛`

三者职责划分如下：

- DeepSeek：理解、纠错、补检索词、判断下一步
- 高德：候选和标准化事实源
- 用户：歧义选择和长尾地址最终确认

该方案既能处理“用户没输入位置”时基于当前位置给候选，也能处理“用户自己输入位置”时的错别字、模糊表达和地图未命中兜底问题，适合作为现有字段提取 Agent 的独立位置子链路。
