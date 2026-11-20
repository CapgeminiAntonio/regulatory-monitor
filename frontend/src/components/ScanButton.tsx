import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { api } from '../api'

export function ScanButton() {
  const qc = useQueryClient()
  const status = useQuery({
    queryKey: ['scan-status'],
    queryFn: api.scanStatus,
    refetchInterval: (q) => (q.state.data?.running ? 1500 : 15000),
  })
  const start = useMutation({
    mutationFn: () => api.startScan(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scan-status'] }),
  })

  const running = status.data?.running ?? false
  const wasRunning = useRef(false)
  useEffect(() => {
    // Refresh the data views as items finish, and once more when the scan completes.
    if (running || wasRunning.current) {
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'scan-status' })
    }
    wasRunning.current = running
  }, [running, status.data?.processed, qc])

  const s = status.data
  return (
    <div className="flex items-center gap-3">
      {s && (running || s.finished_at) && (
        <div className="hidden text-right text-xs text-slate-300 md:block">
          {running ? (
            <>
              <div className="max-w-72 truncate">{s.stage}</div>
              <div>
                {s.processed}/{s.to_process} processed · {s.new} new
              </div>
            </>
          ) : (
            <div title={s.errors.join('\n')}>
              Last scan: {s.new} new, {s.processed} processed
              {s.failed ? `, ${s.failed} failed` : ''}
            </div>
          )}
        </div>
      )}
      <button
        onClick={() => start.mutate()}
        disabled={running || start.isPending}
        className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-sm font-semibold text-blue-900 shadow-sm hover:bg-blue-50 disabled:cursor-wait disabled:opacity-70"
      >
        {running && <span className="size-3 animate-spin rounded-full border-2 border-blue-900 border-t-transparent" />}
        {running ? 'Scanning…' : 'Scan now'}
      </button>
    </div>
  )
}
