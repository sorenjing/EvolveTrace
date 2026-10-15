import type { ActivityFinding, ActivityProject } from "./activity-types";

export function activityPrompt(
  project: Pick<ActivityProject, "name" | "project_id" | "relative_path">,
  finding: Pick<ActivityFinding, "session_id" | "code" | "count" | "window_seconds" | "evidence_refs" | "rule_version">,
): string {
  return [
    "请分析以下 EvolveTrace 执行行为线索：",
    `项目：${project.name} (${project.relative_path})`,
    `项目 ID：${project.project_id}`,
    `会话 ID：${finding.session_id}`,
    `规则：${finding.code} / ${finding.rule_version}`,
    `观察：${finding.window_seconds} 秒采集窗口内出现 ${finding.count} 次相关操作。`,
    `证据事件：${finding.evidence_refs.join(", ")}`,
    "先核对证据，再判断是否属于必要验证、失败重试或可减少的重复工作；证据不足时明确说明。",
    "重复操作规则只表示未观察到修改证据，不能证明文件没有变化。",
    "未采集实际 I/O、磁盘延迟或硬件健康指标，不能据此诊断磁盘损坏。",
    "给出范围最小的改进建议及验证方法；本次请求是分析，执行修正前由用户决定。",
  ].join("\n");
}
