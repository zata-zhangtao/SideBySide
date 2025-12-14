import React from 'react'

interface ProgressProps {
  current: number
  total: number
  label?: string
  height?: number
}

export default function Progress({ current, total, label, height = 16 }: ProgressProps) {
  const pct = Math.max(0, Math.min(100, total > 0 ? (current / total) * 100 : 0))
  return (
    <div className="stack">
      {label && <div className="row" style={{ justifyContent: 'space-between' }}>
        <div>{label}</div>
        <div className="muted">{Math.round(pct)}%</div>
      </div>}
      <div className="progress" style={{ height }}>
        <div className="progress-bar" style={{ width: `${pct}%` }}>
          {current}/{total}
        </div>
      </div>
    </div>
  )
}

