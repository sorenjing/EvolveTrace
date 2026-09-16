import type { ContextDeliveryStatus } from "@/app/lib/harness-types";

export const contextDeliveryCopy: Record<ContextDeliveryStatus, string> = {
  generated: "上下文已生成，尚未交付",
  delivered: "已交付，未证明模型采用",
  acknowledged: "执行客户端已确认任务绑定，未证明遵循内容",
  evidenced: "执行证据引用了上下文标识",
  effective: "对照或回归结果支持有效性结论",
};
