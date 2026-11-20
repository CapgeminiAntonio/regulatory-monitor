// GDPR / EU_AI_ACT are legacy values kept so items from the earlier EU feeds still render.
export type Regulation = 'SEC' | 'FINRA' | 'AML' | 'OTHER' | 'GDPR' | 'EU_AI_ACT'
export type Severity = 'low' | 'medium' | 'high' | 'critical'
export type ImpactLevel = 'none' | 'low' | 'medium' | 'high'

export interface ItemSummary {
  id: number
  source: string
  regulation: Regulation
  url: string
  published: string | null
  status: 'new' | 'analyzed' | 'mapped' | 'failed' | 'stale'
  error: string | null
  raw_title: string
  title: string
  summary: string
  severity: Severity | null
  topics: string[]
  affected_policies: number
  max_impact: ImpactLevel
}

export interface Analysis {
  title: string
  summary: string
  what_changed: string[]
  new_obligations: string[]
  who_is_affected: string
  effective_date: string | null
  comment_deadline: string | null
  regulation: Regulation
  severity: Severity
  topics: string[]
  model: string
}

export interface Impact {
  policy_id: string
  policy_title: string
  policy_owner: string
  impact: ImpactLevel
  affected_sections: string[]
  rationale: string
  recommended_action: string
  confidence: number
}

export interface ItemDetail extends ItemSummary {
  abstract: string
  has_full_text: boolean
  analysis: Analysis | null
  impacts: Impact[]
}

export interface PolicySummary {
  id: string
  title: string
  owner: string
  impacts: { low: number; medium: number; high: number }
}

export interface PolicyDetail {
  id: string
  title: string
  owner: string
  body: string
  changes: {
    item_id: number
    title: string
    regulation: Regulation
    published: string | null
    impact: ImpactLevel
    affected_sections: string[]
    rationale: string
    recommended_action: string
  }[]
}

export interface Matrix {
  policies: { id: string; title: string }[]
  rows: { item_id: number; title: string; regulation: Regulation; severity: Severity | null; cells: Record<string, ImpactLevel> }[]
}

export interface Stats {
  items: number
  by_status: Record<string, number>
  by_regulation: Record<string, number>
  items_with_high_impact: number
  policies: number
}

export interface ScanStatus {
  running: boolean
  stage: string
  started_at: string | null
  finished_at: string | null
  new: number
  updated: number
  processed: number
  to_process: number
  failed: number
  errors: string[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  stats: () => request<Stats>('/api/stats'),
  items: (params: Record<string, string>) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
    return request<ItemSummary[]>(`/api/items${qs ? `?${qs}` : ''}`)
  },
  item: (id: string) => request<ItemDetail>(`/api/items/${id}`),
  reportUrl: (id: number) => `/api/items/${id}/report.md`,
  reportPdfUrl: (id: number) => `/api/items/${id}/report.pdf`,
  policies: () => request<PolicySummary[]>('/api/policies'),
  policy: (id: string) => request<PolicyDetail>(`/api/policies/${id}`),
  matrix: () => request<Matrix>('/api/matrix'),
  scanStatus: () => request<ScanStatus>('/api/scan/status'),
  startScan: (limit?: number) =>
    request<{ started: boolean; status: ScanStatus }>(`/api/scan${limit ? `?limit=${limit}` : ''}`, { method: 'POST' }),
}

export const REG_LABEL: Record<Regulation, string> = {
  SEC: 'SEC',
  FINRA: 'FINRA',
  AML: 'FinCEN / AML',
  OTHER: 'Other',
  GDPR: 'GDPR',
  EU_AI_ACT: 'EU AI Act',
}

/** Regulators currently monitored (used for the filter dropdown). */
export const ACTIVE_REGULATIONS: Regulation[] = ['SEC', 'FINRA', 'AML', 'OTHER']

export function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
