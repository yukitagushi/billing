const SESSION_KEY = "green_permit_intake_session_v1";

export type LocalSession = {
  caseId: string;
  answers: Record<string, string>;
  updatedAt: string;
};

export function loadSession(): LocalSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as LocalSession;
    if (!parsed || typeof parsed.caseId !== "string" || !parsed.answers) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(session: LocalSession): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}
