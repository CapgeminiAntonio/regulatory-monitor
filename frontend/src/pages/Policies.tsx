import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Policies() {
  const { data, isLoading } = useQuery({ queryKey: ['policies'], queryFn: api.policies })
  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Client policy library</h1>
        <p className="text-sm text-slate-600">Northwind Wealth & Asset Management (fictional). Counts show regulatory changes affecting each policy.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data?.map((p) => {
          const total = p.impacts.high + p.impacts.medium + p.impacts.low
          return (
            <Link key={p.id} to={`/policies/${p.id}`} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-300 hover:shadow">
              <div className="font-semibold text-slate-900">{p.title}</div>
              <div className="text-xs text-slate-500">{p.owner}</div>
              <div className="mt-3 flex items-center gap-2 text-xs">
                {total === 0 ? (
                  <span className="text-slate-400">No pending regulatory changes</span>
                ) : (
                  <>
                    {p.impacts.high > 0 && <span className="rounded bg-red-600 px-1.5 py-0.5 font-medium text-white">{p.impacts.high} high</span>}
                    {p.impacts.medium > 0 && <span className="rounded bg-orange-300 px-1.5 py-0.5 font-medium text-orange-950">{p.impacts.medium} medium</span>}
                    {p.impacts.low > 0 && <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">{p.impacts.low} low</span>}
                  </>
                )}
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
