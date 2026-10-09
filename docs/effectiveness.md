# 效果验证：采集正确，审查有用

本文是指标与实验指南，手工统计尚不等于工作台已提供自动指标看板。服务检查见[观测手册](observability.md)，事件边界见[Hook event contract](hook-event-contract.md)，采集验证见[Hook evidence validation](hook-evidence-contract.md)。

## 两种评估分开

EvolveTrace 对某个 Run 的验收检查，回答该 Run 是否有规定证据。评估 EvolveTrace 自身，则要回答它是否正确采集、发现问题，以及是否帮助人完成审查。

已有确定性检查覆盖 Context Freshness、Repository Scope、Verification 等条件；它们不自动给出风险 Precision/Recall 或用户审查收益。Review accepted 和局部修复对比也不能替代工具有/无的公平实验。

## 指标合同

| 指标 | 分子 / 分母或时间边界 | 证据 |
| --- | --- | --- |
| 审查定位时间，主指标 | 审查者收到冻结案例，到正确指出首个预先标注的问题及依据 | 同等资料下分别使用原始记录和工作台；答错/超时另列，不剔除 |
| 审查漏项，保障 | 未发现的预标注实质问题 / 全部预标注问题 | 人工金标，按严重度分层；发现数量多不一定更好 |
| 支持事件采集率，数据质量 | 持久化的预期唯一事件 / 独立清单中客户端应暴露的支持事件 | 合成合同与版本特定真实采集分开；去重，记录客户端/插件版本 |
| 工具输入输出配对率 | 有可关联前后事件的完成调用 / 独立预期的支持完成调用 | 使用关联 ID；未完成调用另列，截断/脱敏字段不算完整正文 |
| Task/Run 绑定率，诊断 | 正确绑定的应绑定 Run / 全部应绑定 Run | 活动 Task、仓库身份及 lease；无 Task 的 Run 不算绑定失败 |
| 风险 Precision / Recall，保障 | TP/(TP+FP)；TP/(TP+FN) | 预定义规则、问题单位、严重度和正负例；按告警类型分别报告 |
| 采集与展示开销 | 采集增加的任务延迟；持久化到界面可见的时间 | 本地时钟条件、样本/失败/断线、事件负载；无实测时记未测 |
| 脱敏保障 | 合成敏感值残留数、正常字段误脱敏数及样本数 | 合同测试；零残留仅证明所测有限格式 |

生命周期缺失不必然说明 Agent 未执行；覆盖范围之外没有可观测分母。不得把“支持事件采集率”称为所有内部行为完整率。事件数、风险数、会话数用于诊断，不是主结果。

## 先验证采集

1. 冻结客户端、插件、后端版本，以及所支持事件与独立预期清单。
2. 先运行既有合成采集与脱敏测试；风险命令只构造测试 payload，不实际执行危险操作。
3. 真实安装下执行普通安全任务，记录预期工具次数/ID、Task 与仓库范围；对照时间线及保存事件。
4. 使用只读观测：

       ./scripts/observe.ps1 -ExpectEvidence

5. 脚本 exit 0 只说明服务可达且至少有 Session，不证明本次任务生命周期完整。检查目标 Session、重复/缺失、配对、Unbound 与脱敏。
6. 缺失分别记为配置、触发、传输、校验、绑定或原因未知；保持 unknown，不补写历史事件。

## 再验证审查收益

建立合成、有正确答案的审查案例：正常调用、失败退出、必需命令未观测、修改越界、上下文 stale、事件缺失、正常命令误告警。任务与 gold labels 冻结后，审查者使用 A 原始脱敏记录或 B 工作台，交叉顺序、隐藏标签和答案。

记录定位是否正确、遗漏、误报处理、人工时间及额外帮助。不要让同一人看过答案后重复同一案例并宣布提速；没有独立审查者时使用匹配案例，明确 n=1 与学习偏差。

## 记录与判断

    experiment_id / case_id / arm / order:
    client_plugin_backend_versions:
    expected_supported_events / observed_unique_events / missing_reason:
    pairing / truncation / redaction / task_binding:
    gold_issues / found_issues / TP / FP / FN / severity:
    correct_localization / active_review_minutes / elapsed / timeout:
    latency_overhead / load / evidence_refs:
    human_review / limitations / conclusion:

零分母 N/A，未采集 null；失败与取消单列。实验前约定可接受漏项、开销和继续条件，不能照搬“99.9%”等未经验证的 SLO。

原始 Hook payload 不落盘；私人轨迹和来源正文不进入公开评测数据。公开示例只用合成数据，结果需经过人工复核。

方法依据：[Google SRE SLI](https://sre.google/workbook/implementing-slos/)支持明确良好事件与总事件；[Anthropic Agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)支持分开轨迹与最终结果。
