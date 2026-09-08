'use client'

import type { ReportValue } from '../types'
import SectionLabel from '../../renderer/src/components/ui/SectionLabel'
import EmptyState from './EmptyState'
import { cardStyle, MUTED, NAVY, TEAL, monoFont } from '../ui'
import { ExternalLink } from './TextLink'
import { Activity } from 'lucide-react'

/** Larger stroke + end-dot so a falling line reads at video resolution. */
function Sparkline({ history }: { history: { date: string; value: number }[] }) {
  if (history.length < 2) {
    return (
      <span style={{ color: MUTED, fontSize: 12, fontFamily: monoFont, fontWeight: 600 }}>—</span>
    )
  }
  const w = 96
  const h = 36
  const vals = history.map((p) => p.value)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const coords = history.map((p, i) => {
    const x = (i / (history.length - 1)) * (w - 6) + 3
    const y = h - ((p.value - min) / range) * (h - 10) - 5
    return { x, y }
  })
  const pts = coords.map((c) => `${c.x},${c.y}`).join(' ')
  const last = coords[coords.length - 1]
  const first = coords[0]
  const falling = history[history.length - 1].value < history[0].value
  const rising = history[history.length - 1].value > history[0].value
  const stroke = falling ? '#c83030' : rising ? '#cc8a00' : TEAL

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden style={{ display: 'block' }}>
      <polyline
        fill="none"
        stroke={`${stroke}33`}
        strokeWidth="6"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={pts}
      />
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth="3"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={pts}
      />
      <circle cx={first.x} cy={first.y} r={3.5} fill="#fff" stroke={stroke} strokeWidth={2} />
      <circle cx={last.x} cy={last.y} r={5} fill={stroke} stroke="#fff" strokeWidth={2} />
    </svg>
  )
}

function flagColor(flag: ReportValue['flag']) {
  if (flag === 'low' || flag === 'high') return '#c83030'
  return TEAL
}

const TREND_LABEL: Record<ReportValue['trend'], string> = {
  rising: '↑ Rising',
  falling: '↓ Falling',
  stable: '→ Stable',
  first_reading: 'First reading',
}

export default function ResultsTable({
  values,
  sourceFileUrl,
}: {
  values: ReportValue[]
  sourceFileUrl?: string
}) {
  return (
    <section style={cardStyle}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 12,
          marginBottom: 4,
          flexWrap: 'wrap',
        }}
      >
        <SectionLabel>Results</SectionLabel>
        {sourceFileUrl && (
          <ExternalLink href={sourceFileUrl} mono>
            View report file →
          </ExternalLink>
        )}
      </div>
      <p style={{ fontSize: 13, color: MUTED, margin: '0 0 16px', lineHeight: 1.55 }}>
        Values, reference ranges, and how each marker is moving.
      </p>

      {!values.length ? (
        <EmptyState
          icon={<Activity size={28} strokeWidth={1.75} />}
          title="No results yet"
          body="When a lab report lands, values and trends will show here."
        />
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 15 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0f0', textAlign: 'left' }}>
                {['Test', 'Value', 'Reference', 'Flag', 'Trend'].map((h) => (
                  <th
                    key={h}
                    style={{
                      fontFamily: monoFont,
                      fontSize: 11,
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      color: MUTED,
                      padding: '10px 14px 12px 0',
                      fontWeight: 700,
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {values.map((row) => {
                const flagged = row.flag === 'low' || row.flag === 'high'
                return (
                  <tr key={row.test_code} style={{ borderBottom: '1px solid #f0f0f8' }}>
                    <td
                      style={{
                        padding: '16px 14px 16px 0',
                        color: NAVY,
                        fontWeight: 600,
                        fontSize: 15,
                      }}
                    >
                      {row.display_name}
                    </td>
                    <td
                      style={{
                        padding: '16px 14px 16px 0',
                        fontFamily: monoFont,
                        fontSize: 18,
                        fontWeight: 700,
                        color: flagged ? '#c83030' : NAVY,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {row.value}{' '}
                      <span style={{ fontWeight: 400, fontSize: 12, color: MUTED }}>{row.unit}</span>
                    </td>
                    <td
                      style={{
                        padding: '16px 14px 16px 0',
                        color: MUTED,
                        fontFamily: monoFont,
                        fontSize: 13,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {row.ref_low}–{row.ref_high}
                    </td>
                    <td style={{ padding: '16px 14px 16px 0' }}>
                      <span
                        style={{
                          fontFamily: monoFont,
                          fontSize: 11,
                          letterSpacing: '0.1em',
                          textTransform: 'uppercase',
                          color: flagColor(row.flag),
                          fontWeight: 700,
                          padding: '4px 8px',
                          borderRadius: 6,
                          background: flagged ? '#fdeaea' : `${TEAL}14`,
                        }}
                      >
                        {row.flag}
                      </span>
                    </td>
                    <td style={{ padding: '16px 0' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <Sparkline history={row.history} />
                        <span
                          style={{
                            fontFamily: monoFont,
                            fontSize: 12,
                            fontWeight: 700,
                            color:
                              row.trend === 'falling'
                                ? '#c83030'
                                : row.trend === 'rising'
                                  ? '#cc8a00'
                                  : MUTED,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {TREND_LABEL[row.trend]}
                        </span>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
