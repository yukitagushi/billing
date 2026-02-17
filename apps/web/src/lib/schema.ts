import { z } from "zod";

export const FieldSchema = z.object({
  form_file: z.string().default(""),
  form_name: z.string().default(""),
  sheet: z.string().default(""),
  cell_range: z.string().default(""),
  field_id: z.string().min(1),
  item_name: z.string().default(""),
  question: z.string().default(""),
  help: z.string().default(""),
  example: z.string().default(""),
  format: z.string().default(""),
  required: z.preprocess((v) => {
    if (typeof v === "boolean") return v;
    if (typeof v === "string") return ["true", "1", "yes", "必須"].includes(v.toLowerCase()) || v.includes("必須");
    return false;
  }, z.boolean()),
  evidence: z.string().default(""),
  what_to_fill: z.string().default(""),
  step_key: z.string().default("step_3"),
  step_title: z.string().default("人員・資金・運賃")
});

export const StepSchema = z.object({
  step_key: z.string(),
  step_title: z.string(),
  field_count: z.number().nonnegative()
});

export const SchemaResponseSchema = z.object({
  field_count: z.number().nonnegative(),
  fields: z.array(FieldSchema),
  steps: z.array(StepSchema)
});

export const ValidationIssueSchema = z.object({
  field_id: z.string(),
  severity: z.enum(["error", "warning"]).default("warning"),
  message: z.string()
});

export type FieldDefinition = z.infer<typeof FieldSchema>;
export type ValidationIssue = z.infer<typeof ValidationIssueSchema>;
