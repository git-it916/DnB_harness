export type RunStatus =
  | "queued"
  | "running"
  | "awaiting_review"
  | "completed"
  | "reviewed"
  | "failed";

export interface Citation {
  document: "신탁계약서" | "IM";
  page: number;
}

export interface CrossCheckValue {
  raw_text: string | null;
  citation: Citation | null;
}

export interface GuardEvent {
  guard: string;
  field_path: string | null;
  decision: string;
  reason_code: string;
  reason: string;
}

export interface ReviewField {
  field: string;
  label: string;
  system_status: string;
  effective_status: "match" | "mismatch" | "needs_human_review" | "missing_evidence";
  resolution_source: string;
  requires_human_review: boolean;
  reason_code: string;
  reason: string;
  contract: CrossCheckValue;
  im: CrossCheckValue;
  canonical: Record<string, unknown> | null;
  judge_suggestion: { status: "same" | "different"; reason: string; reason_code: string } | null;
  guard_events: GuardEvent[];
  human_decision: {
    decision: "same" | "different" | "unknown";
    note: string;
    remember_alias: boolean;
    decided_at: string;
  } | null;
}

export interface ReviewResult {
  run_id: string;
  strategy: string;
  fields: ReviewField[];
  summary: {
    total: number;
    match: number;
    mismatch: number;
    needs_human_review: number;
    missing_evidence: number;
  };
  shacl_conforms: boolean;
  model: string;
  model_digest: string;
  total_latency_ms: number;
  llm_total_tokens: number;
}

export interface ReviewRun {
  id: string;
  status: RunStatus;
  stage: string;
  strategy: string;
  model: string;
  contract_name: string;
  im_name: string;
  error: string | null;
  created_at: string;
  updated_at: string;
  result?: ReviewResult | null;
}
