import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDate } from '../api'
import { ImpactBadge, RegBadge } from '../components/Badges'

/** Minimal markdown rendering for the policy body: headings, bold, and paragraphs. */
function PolicyBody({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed text-slate-700">
      {text.split('\n').filter(Boolean).map((line, i) => {
        const html = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        if (line.startsWith('## '))
          return <h3 key={i} className="pt-3 font-semibold text-slate-900">{line.slice(3)}</h3>
        return <p key={i} dangerouslySetInnerHTML={{ __html: html.replace(/^#+ /, '') }} />
      })}
    </div>
  )
}

export default function PolicyDetail() {
  const { id = '' } = useParams()
  const { data: p, isLoading } = useQuery({ queryKey: ['policy', id], queryFn: () => api.policy(id) })
  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (!p) return <p className="text-sm text-red-600">Not found.</p>

  return (
    <div className="space-y-5">
      <Link to="/policies" className="text-sm text-blue-700 hover:underline">← All policies</Link>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{p.title}</h1>
        <div className="text-sm text-slate-500">Owner: {p.owner}</div>
      </div>
      <div className="grid gap-6 lg:grid-cols-5">
        <section className="space-y-3 lg:col-span-2">
          <h2 className="text-lg font-semibold text-slate-900">Regulatory changes affecting this policy ({p.changes.length})</h2>
          {p.changes.length === 0 && <p className="text-sm text-slate-500">None so far.</p>}
          {p.changes.map((c) => (
            <Link key={c.item_id} to={`/items/${c.item_id}`} className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-300">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <RegBadge reg={c.regulation} />
                <ImpactBadge impact={c.impact} />
                <span>{fmtDate(c.published)}</span>
              </div>
              <div className="mt-1.5 font-medium text-slate-900">{c.title}</div>
              {c.affected_sections.length > 0 && (
                <div className="mt-1 text-xs text-slate-500">Sections {c.affected_sections.map((s) => `§${s.replace(/^§/, '')}`).join(', ')}</div>
              )}
              <p className="mt-2 text-sm text-blue-950">{c.recommended_action}</p>
            </Link>
          ))}
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm lg:col-span-3">
          <PolicyBody text={p.body} />
        </section>
      </div>
    </div>
  )
}
