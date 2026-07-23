import type { ReviewResult, ReviewRun } from "./types";

const API = "/api/v1";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "요청을 처리하지 못했습니다." }));
    throw new Error(body.detail ?? "요청을 처리하지 못했습니다.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => request<ReviewRun[]>(`${API}/runs`),
  getRun: (id: string) => request<ReviewRun>(`${API}/runs/${id}`),
  createRun: (form: FormData) =>
    request<ReviewRun>(`${API}/runs`, { method: "POST", body: form }),
  decide: (
    runId: string,
    field: string,
    payload: { decision: string; note: string; remember_alias: boolean },
  ) =>
    request<ReviewResult>(
      `${API}/runs/${runId}/fields/${encodeURIComponent(field)}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    ),
  documentUrl: (runId: string, role: "contract" | "im", page?: number) =>
    `${API}/runs/${runId}/documents/${role}${page ? `#page=${page}` : ""}`,
};
