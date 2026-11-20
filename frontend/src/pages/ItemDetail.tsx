import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDate } from '../api'
import { ImpactBadge, RegBadge, SeverityBadge, StatusBadge } from '../components/Badges'

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-slate-500">{empty}</p>
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
      {items.map((x, i) => <li key={i}>{x}</li>)}
    </ul>
  )
}

export default function ItemDetail() {
  const { id = '' } = useParams()
  const [showNone, setShowNone] = useState(false)
  const { data: item, isLoading, error } = useQuery({ queryKey: ['item', id], queryFn: () => api.item(id) })

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (error || !item) return <p className="text-sm text-red-600">Not found.</p>
  const a = item.analysis
  const hits = item.impacts.filter((i) => i.impact !== 'none')
  const shown = showNone ? item.impacts : hits

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-blue-700 hover:underline">← All changes</Link>

      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <RegBadge reg={item.regulation} />
          <SeverityBadge severity={item.severity} />
          <StatusBadge status={item.status} error={item.error} />
          <span>{item.source}</span>
          <span>·</span>
          <span>Published {fmtDate(item.published)}</span>
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{item.title}</h1>
        {a && a.title !== item.raw_title && <p className="mt-1 text-sm text-slate-500">Source title: {item.raw_title}</p>}
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <a href={item.url} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">View source ↗</a>
          {a && (
            <>
              <a
                href={api.reportPdfUrl(item.id)}
                className="inline-flex items-center gap-1 rounded-md bg-blue-900 px-2.5 py-1 text-xs font-semibold text-white hover:bg-blue-800"
              >
                Download PDF report
              </a>
              <a href={api.reportUrl(item.id)} download={`impact-report-${item.id}.md`} className="text-blue-700 hover:underline">
                Markdown (.md)
              </a>
            </>
          )}
        </div>
        {item.error && <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{item.error}</p>}

        {a ? (
          <div className="mt-5 grid gap-6 md:grid-cols-3">
            <div className="space-y-5 md:col-span-2">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Summary</h2>
                <p className="mt-1 text-slate-800">{a.summary}</p>
              </div>
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">What changed</h2>
                <List items={a.what_changed} empty="No specific changes identified." />
              </div>
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">New obligations</h2>
                <List items={a.new_obligations} empty="No new obligations identified." />
              </div>
            </div>
            <dl className="space-y-3 rounded-md bg-slate-50 p-4 text-sm">
              <div><dt className="text-slate-500">Who is affected</dt><dd className="text-slate-800">{a.who_is_affected}</dd></div>
              <div><dt className="text-slate-500">Effective date</dt><dd className="text-slate-800">{a.effective_date ?? '—'}</dd></div>
              <div><dt className="text-slate-500">Comment deadline</dt><dd className="text-slate-800">{a.comment_deadline ?? '—'}</dd></div>
              <div>
                <dt className="text-slate-500">Topics</dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {a.topics.map((t) => <span key={t} className="rounded bg-white px-1.5 py-0.5 text-xs ring-1 ring-slate-200">{t}</span>)}
                </dd>
              </div>
              <div><dt className="text-slate-500">Model</dt><dd className="font-mono text-xs text-slate-600">{a.model}</dd></div>
            </dl>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">{item.abstract || 'Not analyzed yet. Run a scan.'}</p>
        )}
      </section>

      {item.impacts.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              Affected client policies <span className="text-slate-400">({hits.length} of {item.impacts.length})</span>
            </h2>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={showNone} onChange={(e) => setShowNone(e.target.checked)} />
              Show unaffected
            </label>
          </div>
          {hits.length === 0 && !showNone && (
            <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
              No client policies need changes for this update.
            </p>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {shown.map((imp) => (
              <div key={imp.policy_id} className={`rounded-lg border bg-white p-4 shadow-sm ${imp.impact === 'high' ? 'border-red-300' : 'border-slate-200'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Link to={`/policies/${imp.policy_id}`} className="font-semibold text-slate-900 hover:text-blue-700">
                      {imp.policy_title}
                    </Link>
                    <div className="text-xs text-slate-500">Owner: {imp.policy_owner}</div>
                  </div>
                  <ImpactBadge impact={imp.impact} />
                </div>
                {imp.impact !== 'none' && (
                  <div className="mt-3 space-y-2 text-sm">
                    {imp.affected_sections.length > 0 && (
                      <div className="text-slate-600">Sections: {imp.affected_sections.map((s) => `§${s.replace(/^§/, '')}`).join(', ')}</div>
                    )}
                    <p className="text-slate-700"><span className="font-medium">Why: </span>{imp.rationale}</p>
                    <p className="rounded-md bg-blue-50 p-2 text-blue-950"><span className="font-medium">Action: </span>{imp.recommended_action}</p>
                    <div className="text-xs text-slate-400">Confidence {Math.round(imp.confidence * 100)}%</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
