import { REG_LABEL, type ImpactLevel, type Regulation, type Severity } from '../api'

const REG_STYLE: Record<Regulation, string> = {
  SEC: 'bg-sky-50 text-sky-800 ring-sky-200',
  FINRA: 'bg-indigo-50 text-indigo-800 ring-indigo-200',
  AML: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  OTHER: 'bg-slate-100 text-slate-700 ring-slate-200',
  GDPR: 'bg-violet-50 text-violet-800 ring-violet-200',
  EU_AI_ACT: 'bg-teal-50 text-teal-800 ring-teal-200',
}

const SEV_STYLE: Record<Severity, string> = {
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
  medium: 'bg-amber-50 text-amber-800 ring-amber-200',
  high: 'bg-orange-100 text-orange-800 ring-orange-300',
  critical: 'bg-red-600 text-white ring-red-700',
}

export const IMPACT_STYLE: Record<ImpactLevel, string> = {
  none: 'bg-slate-100 text-slate-400',
  low: 'bg-amber-100 text-amber-800',
  medium: 'bg-orange-300 text-orange-950',
  high: 'bg-red-600 text-white',
}

const pill = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap'

export function RegBadge({ reg }: { reg: Regulation }) {
  return <span className={`${pill} ${REG_STYLE[reg] ?? REG_STYLE.OTHER}`}>{REG_LABEL[reg] ?? reg}</span>
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity) return null
  return <span className={`${pill} ${SEV_STYLE[severity]} capitalize`}>{severity}</span>
}

export function ImpactBadge({ impact }: { impact: ImpactLevel }) {
  return <span className={`${pill} ring-transparent ${IMPACT_STYLE[impact]} capitalize`}>{impact} impact</span>
}

export function StatusBadge({ status, error }: { status: string; error?: string | null }) {
  if (status === 'mapped') return null
  const style = status === 'failed' ? 'bg-red-50 text-red-700 ring-red-200' : 'bg-slate-100 text-slate-600 ring-slate-200'
  const label =
    status === 'failed'
      ? 'Failed'
      : status === 'new'
        ? 'Awaiting analysis'
        : status === 'stale'
          ? 'Not mapped to current policies'
          : 'Awaiting mapping'
  return <span title={error ?? undefined} className={`${pill} ${style}`}>{label}</span>
}
