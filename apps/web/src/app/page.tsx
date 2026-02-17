"use client";

import { useEffect, useMemo, useState } from "react";

import { createCase, exportCase, getCase, getSchema, saveAnswers, validateCase } from "@/lib/api";
import type { FieldDefinition, ValidationIssue } from "@/lib/schema";
import { loadSession, saveSession } from "@/lib/storage";

type StepGroup = {
  stepKey: string;
  stepTitle: string;
  fields: FieldDefinition[];
};

const STEP_ORDER = ["step_1", "step_2", "step_3"];

function groupFieldsForWizard(fields: FieldDefinition[]): StepGroup[] {
  const buckets = new Map<string, StepGroup>();

  for (const key of STEP_ORDER) {
    buckets.set(key, {
      stepKey: key,
      stepTitle:
        key === "step_1"
          ? "申請者情報"
          : key === "step_2"
            ? "営業所・車両"
            : "人員・資金・運賃",
      fields: []
    });
  }

  for (const field of fields) {
    const key = field.step_key || "step_3";
    const base = buckets.get(key) ?? {
      stepKey: key,
      stepTitle: field.step_title || key,
      fields: []
    };
    base.stepTitle = field.step_title || base.stepTitle;
    base.fields.push(field);
    buckets.set(key, base);
  }

  return [...buckets.values()].filter((g) => g.fields.length > 0);
}

function detectInputType(field: FieldDefinition): "date" | "number" | "textarea" | "text" {
  const fmt = field.format.toLowerCase();
  const text = `${field.item_name} ${field.question} ${field.format}`;

  if (fmt.includes("yyyy") || fmt.includes("date") || text.includes("日付")) {
    return "date";
  }
  if (fmt.includes("数字") || fmt.includes("number") || fmt.includes("金額")) {
    return "number";
  }
  if (text.includes("住所") || text.includes("別紙") || text.includes("詳細")) {
    return "textarea";
  }
  return "text";
}

function statusLabel(status: string): string {
  if (status === "saving") return "保存中";
  if (status === "saved") return "保存済み";
  if (status === "error") return "保存エラー";
  return "待機";
}

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState("");

  const [caseId, setCaseId] = useState("");
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [groups, setGroups] = useState<StepGroup[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [fieldCursor, setFieldCursor] = useState<Record<string, number>>({});

  const [syncStatus, setSyncStatus] = useState("idle");
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [infoMessage, setInfoMessage] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let alive = true;

    async function boot() {
      try {
        const schema = await getSchema();
        if (!alive) return;

        const loadedFields = schema.fields;
        const wizardGroups = groupFieldsForWizard(loadedFields);

        setFields(loadedFields);
        setGroups(wizardGroups);

        const initialCursor: Record<string, number> = {};
        for (const group of wizardGroups) {
          initialCursor[group.stepKey] = 0;
        }
        setFieldCursor(initialCursor);

        const localSession = loadSession();
        let resolvedCaseId = localSession?.caseId ?? "";
        let mergedAnswers: Record<string, string> = localSession?.answers ?? {};

        if (!resolvedCaseId) {
          const created = await createCase(`岩泉案件 ${new Date().toISOString().slice(0, 10)}`);
          resolvedCaseId = created.id;
        }

        if (resolvedCaseId) {
          try {
            const serverCase = await getCase(resolvedCaseId);
            mergedAnswers = {
              ...serverCase.answers_raw,
              ...mergedAnswers
            };
          } catch {
            // Keep local cache if server fetch fails.
          }
        }

        if (!alive) return;
        setCaseId(resolvedCaseId);
        setAnswers(mergedAnswers);
        setLoading(false);
      } catch (err) {
        if (!alive) return;
        setBootError(err instanceof Error ? err.message : "初期化に失敗しました");
        setLoading(false);
      }
    }

    boot();

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!caseId) return;

    saveSession({
      caseId,
      answers,
      updatedAt: new Date().toISOString()
    });

    const timer = window.setTimeout(async () => {
      try {
        setSyncStatus("saving");
        await saveAnswers(caseId, answers);
        setSyncStatus("saved");
      } catch {
        setSyncStatus("error");
      }
    }, 700);

    return () => {
      window.clearTimeout(timer);
    };
  }, [caseId, answers]);

  const requiredFields = useMemo(() => fields.filter((field) => field.required), [fields]);
  const answeredRequired = useMemo(
    () => requiredFields.filter((field) => (answers[field.field_id] || "").trim() !== "").length,
    [answers, requiredFields]
  );
  const progress = requiredFields.length === 0 ? 0 : Math.round((answeredRequired / requiredFields.length) * 100);

  const reviewMode = currentStepIdx >= groups.length;
  const activeGroup = !reviewMode ? groups[currentStepIdx] : null;
  const activeFieldIndex = activeGroup ? fieldCursor[activeGroup.stepKey] ?? 0 : 0;
  const activeField = activeGroup ? activeGroup.fields[Math.min(activeFieldIndex, activeGroup.fields.length - 1)] : null;

  const missingRequired = useMemo(
    () => requiredFields.filter((field) => !(answers[field.field_id] || "").trim()),
    [answers, requiredFields]
  );

  const onChangeAnswer = (fieldId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [fieldId]: value }));
  };

  const goNext = () => {
    if (!activeGroup) return;

    const cursor = fieldCursor[activeGroup.stepKey] ?? 0;
    if (cursor < activeGroup.fields.length - 1) {
      setFieldCursor((prev) => ({ ...prev, [activeGroup.stepKey]: cursor + 1 }));
      return;
    }

    if (currentStepIdx < groups.length - 1) {
      setCurrentStepIdx(currentStepIdx + 1);
      return;
    }

    setCurrentStepIdx(groups.length);
  };

  const goPrev = () => {
    if (reviewMode) {
      const lastStepIdx = Math.max(0, groups.length - 1);
      setCurrentStepIdx(lastStepIdx);
      return;
    }

    if (!activeGroup) return;

    const cursor = fieldCursor[activeGroup.stepKey] ?? 0;
    if (cursor > 0) {
      setFieldCursor((prev) => ({ ...prev, [activeGroup.stepKey]: cursor - 1 }));
      return;
    }

    if (currentStepIdx > 0) {
      setCurrentStepIdx(currentStepIdx - 1);
    }
  };

  const runValidation = async () => {
    if (!caseId) return;
    try {
      setInfoMessage("整合性チェック中...");
      const result = await validateCase(caseId);
      setIssues(result.issues);
      setInfoMessage(`チェック完了: ${result.issue_count}件`);
    } catch (err) {
      setInfoMessage(err instanceof Error ? err.message : "チェックに失敗しました");
    }
  };

  const runExport = async () => {
    if (!caseId) return;
    try {
      setExporting(true);
      setInfoMessage("ZIPを生成中...");
      const blob = await exportCase(caseId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `green_permit_${caseId.slice(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setInfoMessage("ZIPをダウンロードしました");
    } catch (err) {
      setInfoMessage(err instanceof Error ? err.message : "ZIP生成に失敗しました");
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <main>
        <div className="card header-card">
          <h1>Green Permit Intake</h1>
          <p className="muted">初期化中...</p>
        </div>
      </main>
    );
  }

  if (bootError) {
    return (
      <main>
        <div className="card header-card">
          <h1>Green Permit Intake</h1>
          <p className="muted">{bootError}</p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <section className="card header-card">
        <div className="title-row">
          <h1>Green Permit Intake</h1>
          <span className="badge">案件ID: {caseId.slice(0, 8)}</span>
        </div>

        <p className="muted">白ナンバー→緑ナンバー申請の入力を1項目ずつ進めます。</p>

        <div className="progress-wrap">
          <div className="title-row">
            <strong>入力進捗</strong>
            <span className="muted">
              {answeredRequired}/{requiredFields.length} 必須 ({progress}%)
            </span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>

        <div className="step-row">
          {groups.map((group, idx) => (
            <button
              type="button"
              className={`step-chip ${!reviewMode && idx === currentStepIdx ? "active" : ""}`}
              key={group.stepKey}
              onClick={() => setCurrentStepIdx(idx)}
            >
              {idx + 1}. {group.stepTitle}
            </button>
          ))}
          <button
            type="button"
            className={`step-chip ${reviewMode ? "active" : ""}`}
            onClick={() => setCurrentStepIdx(groups.length)}
          >
            4. 確認・生成
          </button>
        </div>

        <p className="muted">自動保存状態: {statusLabel(syncStatus)}</p>
      </section>

      {!reviewMode && activeField && (
        <section className="card field-card">
          <div className="field-meta">
            <small>
              {activeGroup?.stepTitle} / {activeFieldIndex + 1} / {activeGroup?.fields.length}
            </small>
            <h2>{activeField.item_name || activeField.field_id}</h2>
            <p>{activeField.question || activeField.what_to_fill || "入力してください"}</p>
          </div>

          <div className="field-meta-grid">
            <div>
              <p className="label">入力例</p>
              <p>{activeField.example || "-"}</p>
            </div>
            <div>
              <p className="label">形式</p>
              <p>{activeField.format || "text"}</p>
            </div>
            <div>
              <p className="label">根拠資料</p>
              <p>{activeField.evidence || "-"}</p>
            </div>
            <div>
              <p className="label">何を入れる</p>
              <p>{activeField.what_to_fill || "-"}</p>
            </div>
          </div>

          <div className="input-area">
            {detectInputType(activeField) === "textarea" ? (
              <textarea
                className="text-area"
                value={answers[activeField.field_id] || ""}
                onChange={(e) => onChangeAnswer(activeField.field_id, e.target.value)}
                placeholder={activeField.example || "ここに入力"}
              />
            ) : (
              <input
                className="text-input"
                type={detectInputType(activeField)}
                value={answers[activeField.field_id] || ""}
                onChange={(e) => onChangeAnswer(activeField.field_id, e.target.value)}
                placeholder={activeField.example || "ここに入力"}
              />
            )}
          </div>

          <div className="quick-actions">
            <button
              type="button"
              onClick={() => onChangeAnswer(activeField.field_id, activeField.example || "")}
              disabled={!activeField.example}
            >
              例を入力
            </button>
            <button type="button" onClick={() => onChangeAnswer(activeField.field_id, "要確認")}>
              要確認
            </button>
            <button type="button" onClick={() => onChangeAnswer(activeField.field_id, "不明")}>
              不明
            </button>
            <button type="button" onClick={() => onChangeAnswer(activeField.field_id, "対象外")}>
              対象外
            </button>
          </div>

          <div className="nav">
            <button type="button" onClick={goPrev}>
              戻る
            </button>
            <button type="button" className="primary" onClick={goNext}>
              次へ
            </button>
          </div>
        </section>
      )}

      {reviewMode && (
        <section className="card review">
          <h2>確認・生成</h2>
          <p className="muted">
            未入力の必須項目: {missingRequired.length}件 / チェック結果: {issues.length}件
          </p>

          <div className="export">
            <button type="button" onClick={goPrev}>
              入力に戻る
            </button>
            <button type="button" onClick={runValidation}>
              入力チェック
            </button>
            <button type="button" className="primary" onClick={runExport} disabled={exporting}>
              {exporting ? "生成中..." : "ZIP生成"}
            </button>
          </div>

          {infoMessage && <p className="muted">{infoMessage}</p>}

          {missingRequired.slice(0, 20).map((field) => (
            <div key={`missing-${field.field_id}`} className="issue error">
              <strong>未入力: {field.item_name || field.field_id}</strong>
              <p>{field.question}</p>
            </div>
          ))}

          {issues.map((issue, idx) => (
            <div key={`${issue.field_id}-${idx}`} className={`issue ${issue.severity}`}>
              <strong>{issue.severity.toUpperCase()}</strong>
              <p>
                {issue.field_id}: {issue.message}
              </p>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
