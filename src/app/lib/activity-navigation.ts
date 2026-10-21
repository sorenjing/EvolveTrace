interface ProjectMembership {
  project_id: string;
  sessions?: { session_id: string }[];
}

export function projectForSession(projects: ProjectMembership[], sessionId: string, currentId: string | null): string | null {
  const matches = projects.filter(project => project.sessions?.some(session => session.session_id === sessionId));
  if (matches.some(project => project.project_id === currentId)) return currentId;
  return matches.length === 1 ? matches[0].project_id : null;
}
