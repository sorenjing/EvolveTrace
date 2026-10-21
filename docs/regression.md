# 离线证据回归

离线复验对冻结的执行证据重新运行确定性评估器，检查规则升级是否改变了预期结论。它与工作台复用同一个 `evaluate_evidence` 入口。文件里的命令只是被比较的数据，不会执行；无需模型账号，也不会启动 Agent。

## 运行合成案例

在仓库根目录、已准备好后端 Python 环境后运行：

```powershell
./backend/venv/Scripts/python.exe scripts/replay_regressions.py backend/tests/fixtures/regression-cases.json --output runtime/regression-report.json
```

提供的 10 个合成案例覆盖验证成功、失败、结果未知、缺命令、目录错误、验证后又修改、范围越界、缺修改证据、未接入的人工验收，以及起始版本不一致。它们是评估器合同测试，不是 Agent 能力榜单或用户收益实验。

退出码：`0` 表示全部结论匹配；`1` 表示有结论变化或案例错误；`2` 表示整个输入文件无效或无法读取。CI 使用同一命令。

## 从本地 Run 沉淀案例

已完成或已阻断、且仍能找到绑定会话的 Run，可以导出为本地草稿。先启动本地服务，再填写工作台中的 Task / Run ID 和原工作区根目录：

```powershell
./backend/venv/Scripts/python.exe scripts/regression_cases.py export --task-id <task-id> --run-id <run-id> --workspace-root C:/work --case-id failed-verification --output runtime/cases/draft.json
```

服务地址默认 `http://127.0.0.1:8001`，可用 `--url` 指定其他本机 HTTP 端口。客户端禁止代理和重定向。输出文件必须尚不存在。

草稿使用 `regression-draft/v1`，`case.expected` 初始为空，`review.status` 为 `pending`。依据事件、任务要求和独立验收逐项填写预期签名，再填写 `review.reviewer`、`review.basis`，将状态改成 `confirmed`。例如，明确的退出码 1 可以支持必需验证失败；未观察到退出结果时应保留待复核。只读到当前评分结果、或单次人工 accepted，都不能充当独立的预期答案。

```json
{
  "status": "confirmed",
  "reviewer": "local-reviewer",
  "basis": "逐项核对冻结事件及验收合同；验证命令明确返回退出码 1"
}
```

以上片段是草稿里的 `review` 对象，不是完整案例。签名字段和完整结构参见下文及合成案例。确认后运行：

```powershell
./backend/venv/Scripts/python.exe scripts/regression_cases.py freeze runtime/cases/draft.json --output runtime/cases/reviewed.json
./backend/venv/Scripts/python.exe scripts/replay_regressions.py runtime/cases/reviewed.json --output runtime/cases/report.json
```

冻结阶段检查人工声明、标签结构和输入摘要，不要求答案与当前评估器相同。只有标签可在草稿中补充；输入证据变化后需重新导出并复核。保留已确认草稿作为来源和标注依据，生成的 suite 只包含可重评输入与预期签名。人工声明可以审计，但不证明标注者独立或判断一定正确。

导出只保留评分需要的结构化字段，不复制补丁、工具输出正文、提示、转录位置和 Context 正文等专用字段；会话 ID 不保留，事件及调用 ID 改为案例内编号。原始 Run ID、快照摘要及事件数保留在本地草稿中。命令会保留，可能带有内联代码或其他正文；相对路径和验收描述也可能包含私人信息。自动裁剪不等于公开脱敏，公开仓库继续只使用合成案例。文档、测试与 CI 不会自动读取或发布真实数据库。

目录按显式工作区根目录转成相对路径。缺少目录、目录越界、命令等字段含绝对路径样式、超过 1,000 个事件 / 4 MiB、旧文本验收条件等情况会拒绝导出，不能通过截断获得表面完整的案例。导出和冻结都会检查保留的案例字段；现有脱敏规则若识别到敏感值则拒绝，不静默修改验收条件或命令。规则无法识别所有私人内容，仍需人工检查。导出还会比较裁剪前后评分签名；若语义变化则拒绝，需人工构造最小案例。这个一致性检查只防止导出损坏现有证据，不验证当前规则正确性。

## 文件合同

`regression-suite/v1` 包含 `evaluator_suite: evidence/v1` 和 1–100 个案例，总文件最多 4 MiB。每个 `regression-case/v1` 包含：

| 字段 | 内容 |
| --- | --- |
| `case_id` | 唯一、可移植标识 |
| `task` | 现有 Task Contract，验收条件必须结构化 |
| `snapshot` | 现有 ContextBundle v1，固定来源与上下文 |
| `run` | 工作区相对 `cwd` |
| `events` | 最多 1,000 个脱敏事件；保留明确的关联、时间或顺序 |
| `expected` | 每项的 criterion/evaluator ID、版本、状态、严重度和 reason |

目录必须相对；评分时映射到虚拟目录，不读取对应磁盘文件。验收命令不执行，文件存在性及人工条件尚无独立评估器时仍为 `evaluator_unavailable`。编写方式参见合成 JSON；报告不会自动修改预期答案。

报告分别记录输入摘要、预期摘要、结论差异，以及通过、失败、待复核、跳过的数量。坏案例保留在总数里并标记错误，其他案例继续运行。评估器异常与输入错误分别记录，不把“无法判断”算作通过。匹配数衡量评估器与预期的一致性，不是任务成功数。

## 版本与可信度

SessionStart/SessionEnd 采集器分别观察当前 Git 提交和已跟踪文件是否修改；两个 Git 子进程各有 0.4 秒等待上限，失败时保留未知。它不采集或保存源文件正文、不扫描未跟踪文件、不访问远端；Git 判断修改时可能读取已跟踪文件。这不是整个 Hook 的总时限保证。

当 Bundle 包含目标仓库的 `head_commit` 时，评估器将其与同目录 SessionStart 的观察比较。已知不一致阻止接受；目录无法对应、缺观察或脏工作树显示待复核。匹配只支持所声明的提交观察，不证明未跟踪文件、全部业务事实或模型理解仍然有效。快照不原地改写；已有评估保持历史结果，需要新 Run 才重新评估。历史 Bundle 无提交信息时保留旧行为；包含版本合同但评估未保存完整的 Run 不能直接接受，需创建新 Run。

修正比较保留兼容状态 `effective`，同时返回 `comparison_kind: repair` 和 `context_benefit: unmeasured`。工作台展示修正复验已确认；没有固定任务、相同环境及独立验收的对照，不能把修复成功归因给 Context。

## 后续验证

真实任务的独立验证产物接入、公开案例的人工脱敏审查、Agent 重新执行和 Context 消融实验仍需各自的执行合同。当前草稿导出与离线评分入口不执行导入 JSON 指定的脚本。

比较 EvolveTrace 自身的审查收益时，用冻结案例分别比较原始记录和工作台，记录定位是否正确、漏项、净人工时间和采集开销，见[效果验证](effectiveness.md)。公开案例只使用合成数据；实际本地轨迹与记忆可能包含私人内容。

设计参考：[Harbor 任务与验证器](https://docs.harborframework.com/tasks/overview)、[Inspect 评分与错误语义](https://inspect.aisi.org.uk/scoring-policy.html)。
