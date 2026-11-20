import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ACTIVE_REGULATIONS, api, fmtDate, REG_LABEL } from '../api'
import { ImpactBadge, RegBadge, SeverityBadge, StatusBadge } from '../components/Badges'

function Stat({ label, value, tone = 'text-slate-900' }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
    </div>
  )
}

const selectCls = 'rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm'

export default function Feed() {
  const [regulation, setRegulation] = useState('')
  const [severity, setSeverity] = useState('')
  const [q, setQ] = useState('')
  const stats = useQuery({ queryKey: ['stats'], queryFn: api.stats })
  const items = useQuery({ queryKey: ['items', regulation, severity, q], queryFn: () => api.items({ regulation, severity, q }) })

  const s = stats.data
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Changes tracked" value={s?.items ?? '–'} />
        <Stat label="Analyzed & mapped" value={s?.by_status.mapped ?? 0} />
        <Stat label="With high policy impact" value={s?.items_with_high_impact ?? 0} tone="text-red-600" />
        <Stat label="Client policies" value={s?.policies ?? '–'} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          placeholder="Search titles…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className={`${selectCls} w-64`}
        />
        <select value={regulation} onChange={(e) => setRegulation(e.target.value)} className={selectCls}>
          <option value="">All regulations</option>
          {ACTIVE_REGULATIONS.map((r) => (
            <option key={r} value={r}>{REG_LABEL[r]}</option>
          ))}
        </select>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className={selectCls}>
          <option value="">All severities</option>
          {['critical', 'high', 'medium', 'low'].map((v) => (
            <option key={v} value={v} className="capitalize">{v}</option>
          ))}
        </select>
      </div>

      {items.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {items.error && <p className="text-sm text-red-600">Could not reach the backend: {String(items.error)}</p>}
      {items.data?.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          No regulatory changes yet. Click <b>Scan now</b> to pull the latest SEC, FINRA and FinCEN updates.
        </div>
      )}

      <ul className="space-y-3">
        {items.data?.map((it) => (
          <li key={it.id}>
            <Link
              to={`/items/${it.id}`}
              className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-300 hover:shadow"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <RegBadge reg={it.regulation} />
                <SeverityBadge severity={it.severity} />
                <StatusBadge status={it.status} error={it.error} />
                <span>{it.source}</span>
                <span>·</span>
                <span>{fmtDate(it.published)}</span>
              </div>
              <h3 className="mt-2 font-semibold text-slate-900">{it.title}</h3>
              <p className="mt-1 line-clamp-2 text-sm text-slate-600">{it.summary}</p>
              {it.status === 'mapped' && (
                <div className="mt-3 flex items-center gap-2 text-xs">
                  {it.affected_policies > 0 ? (
                    <>
                      <ImpactBadge impact={it.max_impact} />
                      <span className="text-slate-600">
                        {it.affected_policies} polic{it.affected_policies === 1 ? 'y' : 'ies'} affected
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-500">No client policies affected</span>
                  )}
                  {it.topics.slice(0, 4).map((t) => (
                    <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{t}</span>
                  ))}
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
