import type { ActivityFinding, ActivityProject, ActivityReport } from "./activity-types";
import type { AuditStep } from "./audit-flow";

interface ProjectMembership {
  project_id: string;
  sessions?: { session_id: string }[];
}

export function projectForSession(projects: ProjectMembership[], sessionId: string, currentId: string | null): string | null {
  const matches = projects.filter(project => project.sessions?.some(session => session.session_id === sessionId));
  if (matches.some(project => project.project_id === currentId)) return currentId;
  return matches.length === 1 ? matches[0].project_id : null;
}

export function activityFindings(report: ActivityReport | null, projectId: string | null): { finding: ActivityFinding; project: ActivityProject | null }[] {
  if (!report) return [];
  const known = new Set(report.projects.flatMap(project => project.activity.findings.map(finding => finding.finding_id)));
  const rows = report.projects.filter(project => !projectId || project.project_id === projectId)
    .flatMap(project => project.activity.findings.filter(finding => !finding.suppressed).map(finding => ({ finding, project })));
  const unattributed = projectId ? [] : report.overall_activity.findings.filter(finding => !known.has(finding.finding_id) && !finding.suppressed)
    .map(finding => ({ finding, project: null }));
  return [...rows, ...unattributed].sort((a, b) => Number(b.finding.code === "failed_retry") - Number(a.finding.code === "failed_retry"));
}

export function evidenceStepId(steps: AuditStep[], refs: string[]): string | null {
  const identities = new Set(refs);
  return steps.find(step => [step.event, step.start, step.completion].some(event => event && identities.has(event.event_id)))?.id ?? null;
}
