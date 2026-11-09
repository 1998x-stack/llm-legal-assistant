export type Role = 'preparer' | 'reviewer';
export interface Identity { user: string; role: Role }
export interface Block { block_id: string; text: string; page: number | null }
export interface Anchor {
  block_id: string; start_char: number; end_char: number;
  exact_quote: string; quote_sha256: string; page: number | null
}
export interface Finding {
  id: string; rule_id: string; title: string; severity: string;
  anchor: Anchor | null; suggestion: string; decision: string;
  edited_text: string | null; reason: string | null
}
export interface Coverage { rule_id: string; outcome: string; examined_block_ids: string[] }
export interface MatterSummary { id: string; name: string; status: string; revision: number }
export interface Matter extends Omit<MatterSummary, 'id'> {
  matter_id: string; document_version_id: string | null; analysis_id: string | null;
  approval_id: string | null; playbook: string; blocks: Block[];
  findings: Finding[]; coverage: Coverage[];
  context: Record<string, string | boolean> | null;
}

export class ApiError extends Error {
  constructor(public code: string, message: string) { super(message); }
}
export function demoHeaders(identity: Identity, revision?: number): Record<string, string> {
  const result: Record<string, string> = {
    'X-Demo-User': identity.user, 'X-Demo-Role': identity.role
  };
  if (revision !== undefined) result['If-Match'] = String(revision);
  return result;
}
async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as {
      detail?: { code?: string; message?: string } | string
    };
    const detail = data.detail;
    const code = typeof detail === 'object' ? (detail.code || 'API_ERROR') : 'API_ERROR';
    const message = typeof detail === 'object' ? (detail.message || code) : (detail || code);
    throw new ApiError(code, message);
  }
  return response.json() as Promise<T>;
}
async function request<T>(identity: Identity, path: string, method = 'GET',
                          body?: unknown, revision?: number): Promise<T> {
  const headers: Record<string, string> = demoHeaders(identity, revision);
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {
    method, headers, cache: 'no-store',
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  return unwrap<T>(response);
}
export const api = {
  list: (identity: Identity) => request<{items: MatterSummary[]}>(identity, '/v1/matters'),
  create: (identity: Identity, name: string) =>
    request<{matter_id: string}>(identity, '/v1/matters', 'POST', { name }),
  detail: (identity: Identity, id: string) => request<Matter>(identity, '/v1/matters/' + id),
  upload: async (identity: Identity, id: string, file: File) => {
    const data = new FormData(); data.append('file', file);
    return unwrap<{revision: number}>(await fetch('/v1/matters/' + id + '/documents', {
      method: 'POST', headers: demoHeaders(identity), body: data, cache: 'no-store'
    }));
  },
  context: (identity: Identity, id: string, value: unknown, rev: number) =>
    request(identity, '/v1/matters/' + id + '/context', 'PUT', value, rev),
  analyze: (identity: Identity, id: string, rev: number) =>
    request(identity, '/v1/matters/' + id + '/analyses', 'POST', undefined, rev),
  decision: (identity: Identity, id: string, fid: string, payload: unknown, rev: number) =>
    request(identity, '/v1/matters/' + id + '/findings/' + fid + '/decision', 'PATCH', payload, rev),
  approve: (identity: Identity, id: string, rev: number) =>
    request(identity, '/v1/matters/' + id + '/approvals', 'POST',
      { acknowledged_independent_review: true }, rev),
  export: (identity: Identity, id: string, rev: number) =>
    request<{export_id: string}>(identity, '/v1/matters/' + id + '/exports', 'POST', undefined, rev),
  download: async (identity: Identity, id: string, eid: string) => {
    const response = await fetch('/v1/matters/' + id + '/exports/' + eid + '/download', {
      headers: demoHeaders(identity), cache: 'no-store'
    });
    if (!response.ok) throw new ApiError('DOWNLOAD_DENIED', 'Export is no longer available');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'synthetic-review-report.docx';
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  }
};
