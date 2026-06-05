# 非枚举字段自然语言抽取测试报告

## 1. 测试目标

本轮测试的目标是评估：

- 在“枚举字段已由前端结构化采集”的前提下
- 剩余非枚举字段是否能由 LLM 从用户自然语言中稳定抽取

本次测试不再考察以下字段：

- `distributorLevel`
- `mainCategory`
- `mainCategoryGrade`
- `businessType`
- `cooperationStatus`
- `status`
- `informationSource`
- `providePoints`
- `providePointsRatio`
- 其他已规划为前端枚举选择的字段

本轮重点关注的字段包括：

- 主体基础字段
- 上下级关系与销售归属字段
- 联系人字段
- 日期、折扣、地址、备注字段
- 修改场景下的覆盖抽取能力

## 2. 测试方式

### 2.1 模型与环境

- 模型：`deepseek-v4-flash`
- 调用方式：真实 DeepSeek 接口
- 执行环境：Docker 容器内运行

### 2.2 数据集规模

共 250 条测试样本，分为 5 个场景，每个场景 50 条：

1. `company_core`
2. `relationship_sales`
3. `contacts`
4. `dates_discount_site`
5. `modifications`

### 2.3 执行命令

```bash
docker compose exec app python -m evals.run_extraction_eval \
  --case-file /workspace/evals/cases/extraction_non_enum_5x50.jsonl \
  --sleep-seconds 0.1 \
  --max-attempts 3 \
  --progress-every 25
```

### 2.4 结果文件

- 数据集：[extraction_non_enum_5x50.jsonl](/Users/ganzhiwen/workspace/InformationEntryAgent/evals/cases/extraction_non_enum_5x50.jsonl:1)
- 结果：[extraction_non_enum_5x50_20260604T070657Z.json](/Users/ganzhiwen/workspace/InformationEntryAgent/evals/results/extraction_non_enum_5x50_20260604T070657Z.json:1)

## 3. 总体结果

### 3.1 总体指标

- 总样本数：250
- 完全一致率 `exact_match_rate`：0.084
- 字段精确率 `field_precision`：0.9584
- 字段召回率 `field_recall`：0.8101
- 字段 F1：0.8780
- 必填字段召回率 `required_field_recall`：0.9940
- 平均单条耗时：5.033 秒
- 网络/调用失败样本数：0

### 3.2 结果解读

这组结果说明：

- 模型“乱提字段”的情况较少，精确率很高
- 主要问题是“漏提”和“字段落位不准”，召回率明显低于精确率
- 对业务主链路影响最大的必填字段整体较稳
- 但复杂补充字段、地址拆分字段、修改场景字段仍不稳定

## 4. 分场景结果

### 4.1 `company_core`

- 样本数：50
- 完全一致率：0.00
- 字段 F1：0.9091
- 平均耗时：3.687 秒

结论：

- 基础主体字段整体较稳
- 失败集中在 `source`

### 4.2 `relationship_sales`

- 样本数：50
- 完全一致率：0.00
- 字段 F1：0.8889
- 平均耗时：4.564 秒

结论：

- 上级经销商、所属销售、所属经理、授权区域整体较稳
- 失败集中在 `salesProductTypeName`

### 4.3 `contacts`

- 样本数：50
- 完全一致率：0.42
- 字段 F1：0.9642
- 平均耗时：3.837 秒

结论：

- 这是当前表现最好的场景
- 联系人姓名、职位、电话、微信整体抽取稳定
- 少量失败来自 `isPrimary` 漏提

### 4.4 `dates_discount_site`

- 样本数：50
- 完全一致率：0.00
- 字段 F1：0.8042
- 平均耗时：6.612 秒

结论：

- 这是当前问题较多的场景之一
- 日期与折扣本身还可以
- 地址拆分、备注归属、完整地址保真度不稳定

### 4.5 `modifications`

- 样本数：50
- 完全一致率：0.00
- 字段 F1：0.8348
- 平均耗时：6.465 秒

结论：

- 修改型输入是当前另一类明显薄弱场景
- 主体字段覆盖更新还可以
- 联系人修改与地址拆分更新仍不稳定

## 5. 当前主要问题

### 5.1 `source` 被错误映射为 `informationSource`

表现：

- `company_core` 场景下，`main_info.source` 50 条全部未命中

典型现象：

- 预期字段：`source`
- 模型输出字段：`informationSource`

说明：

- 模型理解了“来源”语义
- 但字段落位错了
- 这是字段定义约束问题，不是纯语义理解失败

### 5.2 `salesProductTypeName` 被错误归类

表现：

- `relationship_sales` 场景下，`main_info.salesProductTypeName` 50 条全部未命中

典型现象：

- 用户表达“销售产品类型做五金”
- 模型更容易输出到 `mainCategory`

说明：

- 这是字段边界不清导致的错位
- 模型把“销售产品类型”理解成“主营品类”

### 5.3 地址拆分能力不足

表现：

- `sites[0].provinceName`、`cityName`、`districtName` 高频漏提
- `modifications` 场景中三项各失败 50 次

说明：

- 模型能识别完整地址
- 但对省、市、区的结构化拆分不稳定
- 在“修改地址”场景下尤其明显

### 5.4 备注字段归属不稳定

表现：

- `main_info.remark` 失败 50 次
- `sites[0].remark` 有 41 次误提

说明：

- 模型能识别“备注语义”
- 但不知道该落到主体备注还是场地备注
- 这反映出 prompt 中对备注字段边界定义不够清晰

### 5.5 主联系人标记存在漏提

表现：

- `contacts[0].isPrimary` 失败 16 次
- `contacts[1].isPrimary` 失败 15 次

说明：

- 联系人主体信息抽得不错
- 但“主要对接”“主联系人”这类隐式主联系人判定不够稳定

### 5.6 完全一致率偏低，但不代表主链路不可用

表现：

- `exact_match_rate` 仅 8.4%

说明：

- 这是因为本轮评测按严格完全一致判分
- 只要漏一个补充字段或地址拆分字段，就算整条失败
- 因此它更适合衡量“整体完整性”，不适合单独判断“是否可用”

从业务角度看，更值得关注的是：

- 必填字段召回率很高
- 联系人与主体基础字段已经较稳
- 当前主要瓶颈在补充字段和复杂修改字段

## 6. 典型失败样例

### 6.1 主体来源字段失败

输入：

```text
新增经销商，名字叫远航汽配1号店，客户邮箱是yuanhang01@example.com，客户手机号13800000001，ERP编码YH001，所属区域华东，来源老客户介绍。
```

问题：

- 预期：`main_info.source = 老客户介绍`
- 实际：模型写成了 `informationSource`

### 6.2 销售产品类型失败

输入：

```text
这是二级经销商，上级经销商挂在联诚工具中心1下面，所属销售是王磊，经理是陈涛，销售产品类型做五金，授权区域杭州及周边。
```

问题：

- 预期：`salesProductTypeName = 五金`
- 实际：模型倾向于把“五金”理解到 `mainCategory`

### 6.3 地址与备注失败

输入：

```text
签发日期是2026年1月1日，到期日期到2027/1/1，折扣给55%。门店地址在浙江省杭州市西湖区文三路18号，备注仓库和门店在一起1。
```

问题：

- 完整地址被截成 `文三路18号`
- `remark` 被写到 `sites[0].remark`
- `main_info.remark` 未命中

### 6.4 修改地址拆分失败

输入：

```text
经销商名称改成星驰工业1，客户手机号改成13500000001，客户邮箱换成xingchi01@new.com，ERP编码改为XCNEW001，所属区域不是华东，改成华南。赵敏 的电话改成 18800000001，门店地址改到浙江省杭州市西湖区金鸡湖大道66号。
```

问题：

- 完整地址可识别
- 但 `provinceName/cityName/districtName` 没有正确拆出

## 7. 结论

当前非枚举字段抽取能力可以分成三层判断：

### 7.1 已经比较稳定的部分

- 经销商名称
- 客户邮箱
- 客户手机号
- ERP 编码
- 所属区域
- 联系人姓名/职位/电话/微信

### 7.2 可用但还不够稳的部分

- 上级经销商名称
- 所属销售/所属经理
- 授权区域
- 日期
- 折扣
- 修改型主体字段覆盖

### 7.3 当前明显薄弱的部分

- `source` 与 `informationSource` 的字段区分
- `salesProductTypeName`
- 地址拆分字段
- `remark` 的字段归属
- 修改场景下的地址结构化

## 8. 下一步建议

### 8.1 优先级 P0

- 明确 prompt 中 `source` 与 `informationSource` 的边界
- 明确 `salesProductTypeName` 与 `mainCategory` 的区别
- 为地址拆分增加规则或后处理逻辑

### 8.2 优先级 P1

- 为 `remark` 增加字段归属约束
- 为“主联系人”补规则或增强提示
- 强化修改场景的 patch 输出约束

### 8.3 优先级 P2

- 把本轮 250 条评测集作为固定回归集
- 每次优化后重跑
- 按场景观察 F1 是否提升，而不是只看总分

## 9. 最终判断

在“枚举字段由前端结构化采集”的前提下，当前 LLM 对剩余自然语言字段的表现可以认为：

- 主链路可继续推进
- 联系人和基础主体信息已具备较好可用性
- 复杂补充字段与修改场景还需要继续收敛

现阶段最重要的不是继续扩大字段范围，而是优先修复：

- 字段错位
- 地址拆分
- 备注归属
- 修改场景稳定性

这些问题修好后，整体质量会有比继续加字段更明显的提升。
