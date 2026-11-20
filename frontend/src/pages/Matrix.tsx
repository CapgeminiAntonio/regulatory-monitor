import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api, type ImpactLevel } from '../api'
import { IMPACT_STYLE, RegBadge } from '../components/Badges'

const LEVELS: ImpactLevel[] = ['high', 'medium', 'low', 'none']

export default function MatrixPage() {
  const { data, isLoading } = useQuery({ queryKey: ['matrix'], queryFn: api.matrix })
  const navigate = useNavigate()

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (!data?.rows.length)
    return <p className="text-sm text-slate-500">No mapped changes yet. Run a scan to populate the matrix.</p>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Impact matrix</h1>
          <p className="text-sm text-slate-600">Each regulatory change (row) against each client policy (column). Click a row for details.</p>
        </div>
        <div className="flex gap-3 text-xs">
          {LEVELS.map((l) => (
            <span key={l} className="flex items-center gap-1.5 capitalize text-slate-600">
              <span className={`inline-block size-3 rounded-sm ${IMPACT_STYLE[l]}`} />{l}
            </span>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 min-w-80 bg-white p-3 text-left align-bottom font-semibold text-slate-700">Regulatory change</th>
              {data.policies.map((p) => (
                <th key={p.id} className="h-44 w-12 p-1 align-bottom">
                  <Link
                    to={`/policies/${p.id}`}
                    title={p.title}
                    className="mx-auto block max-h-40 overflow-hidden text-xs font-medium text-slate-600 [writing-mode:vertical-rl] rotate-180 hover:text-blue-700"
                  >
                    {p.title}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.item_id} onClick={() => navigate(`/items/${r.item_id}`)} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                <td className="sticky left-0 bg-inherit p-3">
                  <div className="flex items-center gap-2">
                    <RegBadge reg={r.regulation} />
                    <span className="line-clamp-1 text-slate-800" title={r.title}>{r.title}</span>
                  </div>
                </td>
                {data.policies.map((p) => {
                  const level = r.cells[p.id]
                  return (
                    <td key={p.id} className="p-1">
                      <div title={`${p.title}: ${level}`} className={`mx-auto size-8 rounded ${IMPACT_STYLE[level]} ${level === 'none' ? 'opacity-40' : ''}`} />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
