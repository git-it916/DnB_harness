import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { ReviewField, ReviewRun } from "./types";

const STAGES = [
  "queued",
  "extracting_documents",
  "applying_guards",
  "comparing_policy",
  "resolving_aliases",
  "selective_judge",
  "building_audit",
  "complete",
];

const statusCopy = {
  match: ["일치", "status-match"],
  mismatch: ["불일치", "status-mismatch"],
  needs_human_review: ["사용자 확인", "status-review"],
  missing_evidence: ["근거 부족", "status-missing"],
} as const;

function App() {
  const [runs, setRuns] = useState<ReviewRun[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<ReviewRun | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(true);
  const [error, setError] = useState("");

  const refreshRuns = async () => {
    const next = await api.listRuns();
    setRuns(next);
    if (!selectedId && next.length) {
      setSelectedId(next[0].id);
      setShowNew(false);
    }
  };

  useEffect(() => {
    refreshRuns().catch((reason) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!selectedId || showNew) return;
    let cancelled = false;
    const load = async () => {
      try {
        const run = await api.getRun(selectedId);
        if (cancelled) return;
        setSelectedRun(run);
        setSelectedField((current) => current ?? run.result?.fields[0]?.field ?? null);
        if (["queued", "running"].includes(run.status)) {
          window.setTimeout(load, 1200);
        } else {
          refreshRuns().catch(() => undefined);
        }
      } catch (reason) {
        if (!cancelled) setError((reason as Error).message);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [selectedId, showNew]);

  const openRun = (id: string) => {
    setSelectedId(id);
    setSelectedRun(null);
    setSelectedField(null);
    setShowNew(false);
  };

  const activeField = useMemo(
    () => selectedRun?.result?.fields.find((field) => field.field === selectedField) ?? null,
    [selectedRun, selectedField],
  );

  return (
    <div className="app-shell">
      <Sidebar
        runs={runs}
        selectedId={selectedId}
        onSelect={openRun}
        onNew={() => setShowNew(true)}
      />
      <main className="workspace">
        {error && <div className="global-error" role="alert">{error}</div>}
        {showNew ? (
          <NewReview
            onCreated={(run) => {
              setRuns((current) => [run, ...current]);
              openRun(run.id);
            }}
          />
        ) : selectedRun ? (
          <ReviewWorkspace
            run={selectedRun}
            activeField={activeField}
            onSelectField={setSelectedField}
            onResultUpdate={(result) =>
              setSelectedRun((current) => (current ? { ...current, result } : current))
            }
          />
        ) : (
          <LoadingState />
        )}
      </main>
    </div>
  );
}

function Sidebar({
  runs,
  selectedId,
  onSelect,
  onNew,
}: {
  runs: ReviewRun[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">D</span>
        <span className="brand-copy">
          <strong>DnB Harness</strong>
          <small>Document assurance</small>
        </span>
      </div>
      <button className="new-review" onClick={onNew}><span aria-hidden="true">＋</span> 새 검토</button>
      <div className="history-label">검토 이력</div>
      <nav className="run-list">
        {runs.map((run) => (
          <button
            key={run.id}
            className={run.id === selectedId ? "run-item active" : "run-item"}
            onClick={() => onSelect(run.id)}
            aria-current={run.id === selectedId ? "page" : undefined}
          >
            <span className={`run-dot ${run.status}`} />
            <span className="run-copy">
              <strong>{run.contract_name.replace(/\.pdf$/i, "")}</strong>
              <small>{formatDate(run.created_at)} · {runStatusLabel(run.status)}</small>
            </span>
          </button>
        ))}
        {!runs.length && <p className="empty-history">아직 실행한 검토가 없습니다.</p>}
      </nav>
    </aside>
  );
}

function NewReview({ onCreated }: { onCreated: (run: ReviewRun) => void }) {
  const [contract, setContract] = useState<File | null>(null);
  const [im, setIm] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!contract || !im) return;
    setSubmitting(true);
    setError("");
    const form = new FormData();
    form.append("contract", contract);
    form.append("im", im);
    form.append("strategy", "ontology_policy_judge");
    form.append("model", "claude-sonnet-4-6");
    try {
      onCreated(await api.createRun(form));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="new-page page-enter">
      <header className="page-header">
        <p className="eyebrow">LOCAL DOCUMENT REVIEW</p>
        <h1>문서 정합성 검토</h1>
      </header>
      <form className="upload-form" onSubmit={submit}>
        <FileDrop label="신탁계약서" hint="검토 기준 문서" file={contract} onChange={setContract} />
        <div className="document-link" aria-hidden="true"><span>기준</span><i /></div>
        <FileDrop label="투자제안서 (IM)" hint="대조할 문서" file={im} onChange={setIm} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-action" disabled={!contract || !im || submitting}>
          {submitting ? "업로드 중…" : "검토 시작"}
        </button>
      </form>
    </section>
  );
}

function FileDrop({ label, hint, file, onChange }: { label: string; hint: string; file: File | null; onChange: (file: File | null) => void }) {
  return (
    <label className={file ? "file-drop filled" : "file-drop"}>
      <input type="file" accept="application/pdf,.pdf" aria-label={`${label} PDF 선택`} onChange={(event) => onChange(event.target.files?.[0] ?? null)} />
      <span className="file-icon">PDF</span>
      <strong>{file?.name ?? label}</strong>
      <small>{file ? formatBytes(file.size) : `${hint} · PDF 최대 50MB`}</small>
      <em>{file ? "변경" : "파일 선택"}</em>
    </label>
  );
}

function ReviewWorkspace({ run, activeField, onSelectField, onResultUpdate }: { run: ReviewRun; activeField: ReviewField | null; onSelectField: (field: string) => void; onResultUpdate: (result: NonNullable<ReviewRun["result"]>) => void }) {
  if (run.status === "failed") {
    return <FailureState run={run} />;
  }
  if (!run.result) {
    return <ProgressState run={run} />;
  }
  return (
    <div className="review-layout page-enter">
      <section className="results-pane">
        <RunHeader run={run} />
        <Summary result={run.result} />
        <div className="field-table-heading"><h2>필드 판정</h2><span>총 {run.result.summary.total}개</span></div>
        <div className="field-table">
          {run.result.fields.map((field) => {
            const [label, className] = statusCopy[field.effective_status];
            return (
              <button key={field.field} className={activeField?.field === field.field ? "field-row selected" : "field-row"} onClick={() => onSelectField(field.field)} aria-pressed={activeField?.field === field.field}>
                <span className="field-name"><strong>{field.label}</strong><small>{groupLabel(field.field)}</small></span>
                <span className={`status-label ${className}`}><i />{label}</span>
                <span className="row-arrow">›</span>
              </button>
            );
          })}
        </div>
      </section>
      <Inspector run={run} field={activeField} onResultUpdate={onResultUpdate} />
    </div>
  );
}

function RunHeader({ run }: { run: ReviewRun }) {
  return (
    <header className="run-header">
      <div><p className="eyebrow">DOCUMENT REVIEW</p><h1>{run.contract_name.replace(/\.pdf$/i, "")}</h1></div>
    </header>
  );
}

function Summary({ result }: { result: NonNullable<ReviewRun["result"]> }) {
  const items = [
    ["불일치", result.summary.mismatch, "mismatch"],
    ["사용자 확인", result.summary.needs_human_review, "review"],
    ["근거 부족", result.summary.missing_evidence, "missing"],
    ["일치", result.summary.match, "match"],
  ];
  return (
    <div className="summary-strip">
      {items.map(([label, count, tone]) => <div key={label}><span className={`summary-dot ${tone}`} /><strong>{count}</strong><small>{label}</small></div>)}
      <div className="shacl-state"><span>문서 내부 제약</span><strong>{result.shacl_conforms ? "통과" : "위반 있음"}</strong></div>
    </div>
  );
}

function Inspector({ run, field, onResultUpdate }: { run: ReviewRun; field: ReviewField | null; onResultUpdate: (result: NonNullable<ReviewRun["result"]>) => void }) {
  const [decision, setDecision] = useState<"same" | "different" | "unknown">("same");
  const [remember, setRemember] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setDecision("same"); setRemember(false); setNote(""); setError(""); }, [field?.field]);
  if (!field) return <aside className="inspector empty-inspector">필드를 선택하면 근거가 표시됩니다.</aside>;
  const [statusLabel, statusClass] = statusCopy[field.effective_status];
  const save = async () => {
    setSaving(true); setError("");
    try {
      onResultUpdate(await api.decide(run.id, field.field, { decision, note, remember_alias: remember }));
    } catch (reason) { setError((reason as Error).message); }
    finally { setSaving(false); }
  };
  return (
    <aside className="inspector inspector-enter" key={field.field}>
      <header className="inspector-header"><div><small>{groupLabel(field.field)}</small><h2>{field.label}</h2></div><span className={`status-label ${statusClass}`}><i />{statusLabel}</span></header>
      <EvidenceBlock title="신탁계약서" role="contract" value={field.contract} runId={run.id} />
      <EvidenceBlock title="투자제안서 (IM)" role="im" value={field.im} runId={run.id} />
      {field.judge_suggestion && <section className="judge-note"><strong>AI 보조 의견 · {field.judge_suggestion.status === "same" ? "동일 가능" : "차이 가능"}</strong><p>{field.judge_suggestion.reason}</p><small>자동 확정하지 않은 참고 의견입니다.</small></section>}
      {field.requires_human_review && (
        <section className="human-review">
          <div className="review-heading"><span>사용자 확인</span><strong>두 문서가 같은 내용을 말합니까?</strong></div>
          <div className="decision-options">
            <button type="button" aria-pressed={decision === "same"} className={decision === "same" ? "active" : ""} onClick={() => setDecision("same")}>같음</button>
            <button type="button" aria-pressed={decision === "different"} className={decision === "different" ? "active" : ""} onClick={() => { setDecision("different"); setRemember(false); }}>다름</button>
            <button type="button" aria-pressed={decision === "unknown"} className={decision === "unknown" ? "active" : ""} onClick={() => { setDecision("unknown"); setRemember(false); }}>판단 보류</button>
          </div>
          <textarea placeholder="판단 근거 또는 메모 (선택)" value={note} onChange={(event) => setNote(event.target.value)} />
          {decision === "same" && isAliasField(field.field) && <label className="remember-alias"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /><span>앞으로도 이 두 표현을 같은 명칭으로 사용</span></label>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="button" className="confirm-decision" disabled={saving} onClick={save}>{saving ? "저장 중…" : "판정 저장"}</button>
        </section>
      )}
      {field.human_decision && <section className="human-record"><span>사용자 판정 기록</span><strong>{field.human_decision.decision === "same" ? "같음" : field.human_decision.decision === "different" ? "다름" : "판단 보류"}</strong><p>{field.human_decision.note || "별도 메모 없음"}</p></section>}
    </aside>
  );
}

function EvidenceBlock({ title, role, value, runId }: { title: string; role: "contract" | "im"; value: ReviewField["contract"]; runId: string }) {
  return (
    <section className="evidence-block">
      <div><h3>{title}</h3>{value.citation && <a href={api.documentUrl(runId, role, value.citation.page)} target="_blank" rel="noreferrer">p.{value.citation.page} 열기 ↗</a>}</div>
      <blockquote>{value.raw_text ?? "원문 근거가 없습니다."}</blockquote>
    </section>
  );
}

function ProgressState({ run }: { run: ReviewRun }) {
  const current = Math.max(0, STAGES.indexOf(run.stage));
  return (
    <section className="progress-page page-enter" aria-live="polite"><div className="progress-orbit" aria-hidden="true"><span /><i /></div><p className="eyebrow">REVIEW IN PROGRESS</p><h1>문서를 검토하고 있습니다</h1><p>{stageLabel(run.stage)}</p><div className="stage-track" role="progressbar" aria-valuemin={0} aria-valuemax={STAGES.length - 1} aria-valuenow={current}>{STAGES.slice(0, -1).map((stage, index) => <span key={stage} className={index <= current ? "done" : ""} />)}</div><small>브라우저를 닫아도 실행 이력은 로컬에 유지됩니다.</small></section>
  );
}

function FailureState({ run }: { run: ReviewRun }) {
  return <section className="failure-page"><p className="eyebrow">REVIEW FAILED</p><h1>검토를 완료하지 못했습니다</h1><p>{run.error}</p><small>Anthropic API 키와 모델 설정을 확인한 뒤 다시 시도하세요.</small></section>;
}

function LoadingState() { return <section className="loading-state">검토 정보를 불러오는 중…</section>; }

function groupLabel(field: string) { const group: Record<string, string> = { fund: "펀드 기본", party: "당사자", fee_schedule: "보수", redemption_terms: "환매 조건" }; return group[field.split(".")[0]] ?? field; }
function runStatusLabel(status: string) { return ({ queued: "대기", running: "검토 중", awaiting_review: "확인 필요", completed: "완료", reviewed: "확인 완료", failed: "실패" } as Record<string, string>)[status] ?? status; }
function stageLabel(stage: string) { return ({ queued: "실행 순서를 기다리는 중", extracting_documents: "계약서와 IM에서 핵심 필드를 추출하는 중", applying_guards: "형식·출처·업무 제약을 검사하는 중", comparing_policy: "온톨로지 필드 정책으로 값을 비교하는 중", resolving_aliases: "승인된 명칭 정보를 확인하는 중", selective_judge: "미해결 항목만 선택적으로 판단하는 중", building_audit: "감사 가능한 결과를 정리하는 중" } as Record<string, string>)[stage] ?? stage; }
function formatDate(value: string) { return new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function formatBytes(bytes: number) { return `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
function isAliasField(field: string) { return ["fund.name", "party.asset_manager", "party.trustee", "party.distributor"].includes(field); }

export default App;
