import { z } from "zod";

import { SchemaResponseSchema, ValidationIssueSchema } from "./schema";

const CaseSchema = z.object({
  id: z.string(),
  title: z.string(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string()
});

const CaseDetailSchema = z.object({
  case: CaseSchema,
  answers_raw: z.record(z.string()),
  answers_norm: z.record(z.string())
});

const UpdateAnswersResponseSchema = z.object({
  updated: z.number(),
  issues: z.array(ValidationIssueSchema)
});

const ValidateResponseSchema = z.object({
  issue_count: z.number(),
  issues: z.array(ValidationIssueSchema)
});

const CreateCaseResponseSchema = z.object({
  case: CaseSchema
});

export type CaseEntity = z.infer<typeof CaseSchema>;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function fetchJson(input: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(`${API_BASE}${input}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json();
}

export async function getSchema() {
  const json = await fetchJson("/schema");
  return SchemaResponseSchema.parse(json);
}

export async function createCase(title: string) {
  const json = await fetchJson("/cases", {
    method: "POST",
    body: JSON.stringify({ title })
  });
  return CreateCaseResponseSchema.parse(json).case;
}

export async function getCase(caseId: string) {
  const json = await fetchJson(`/cases/${caseId}`);
  return CaseDetailSchema.parse(json);
}

export async function saveAnswers(caseId: string, answers: Record<string, string>) {
  const json = await fetchJson(`/cases/${caseId}/answers`, {
    method: "PUT",
    body: JSON.stringify({ answers })
  });
  return UpdateAnswersResponseSchema.parse(json);
}

export async function validateCase(caseId: string) {
  const json = await fetchJson(`/cases/${caseId}/validate`, {
    method: "POST"
  });
  return ValidateResponseSchema.parse(json);
}

export async function exportCase(caseId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/exports/${caseId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ include_debug_json: true })
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Export error ${res.status}: ${text}`);
  }

  return res.blob();
}
