'use client'

import type { TimelineEntry } from '../types'
import { actionLabel } from '../stateLabels'
import SectionLabel from '../../renderer/src/components/ui/SectionLabel'
import EmptyState from './EmptyState'
import {
  ACTOR_LABELS,
  agentAccent,
  cardStyle,
  formatTimestamp,
  MUTED,
  monoFont,
  NAVY,
  patientAccent,
  sansFont,
} from '../ui'
import { LinkifiedText } from './TextLink'
import { Bot, History, User } from 'lucide-react'

function isAgent(actor: TimelineEntry['actor']) {
  return actor !== 'patient'
}

export default function EpisodeTimeline({ entries }: { entries: TimelineEntry[] }) {
  const sorted = [...entries].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime())

  return (
    <section style={cardStyle}>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          gap: 12,
          marginBottom: 8,
        }}
      >
        <div>
          <SectionLabel>Timeline</SectionLabel>
          <p style={{ fontSize: 14, color: MUTED, margin: 0, lineHeight: 1.55, maxWidth: 420 }}>
            Every step NaniAi took — and anything you uploaded — in order.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <LegendDot color={agentAccent} square label="Agent" />
          <LegendDot color={patientAccent} square={false} label="You" />
        </div>
      </div>

      {!sorted.length ? (
        <EmptyState
          icon={<History size={28} strokeWidth={1.75} />}
          title="No events yet"
          body="As soon as NaniAi starts working this episode, each action will appear here."
        />
      ) : (
        <div style={{ position: 'relative', paddingLeft: 40, marginTop: 20 }}>
          <div
            style={{
              position: 'absolute',
              left: 17,
              top: 14,
              bottom: 14,
              width: 3,
              background: `linear-gradient(180deg, ${agentAccent}55 0%, ${patientAccent}44 100%)`,
              borderRadius: 3,
            }}
          />
          {sorted.map((entry, i) => {
            const agent = isAgent(entry.actor)
            const accent = agent ? agentAccent : patientAccent
            const isLast = i === sorted.length - 1
            return (
              <div
                key={`${entry.at}-${entry.action}-${i}`}
                style={{
                  position: 'relative',
                  paddingBottom: isLast ? 0 : 22,
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: -32,
                    top: 4,
                    width: 34,
                    height: 34,
                    borderRadius: agent ? 10 : 999,
                    background: agent ? accent : '#fff',
                    border: `2.5px solid ${accent}`,
                    boxShadow: agent
                      ? `0 0 0 4px ${accent}18`
                      : `0 0 0 4px ${accent}22`,
                    display: 'grid',
                    placeItems: 'center',
                    color: agent ? '#fff' : accent,
                    zIndex: 1,
                  }}
                >
                  {agent ? <Bot size={15} strokeWidth={2.4} /> : <User size={15} strokeWidth={2.4} />}
                </div>

                <div
                  style={{
                    padding: '14px 18px',
                    borderRadius: 12,
                    background: agent
                      ? `linear-gradient(135deg, ${accent}0a 0%, #fafafe 48%)`
                      : `linear-gradient(135deg, ${accent}12 0%, #fff 55%)`,
                    border: `1.5px solid ${agent ? `${accent}28` : `${accent}40`}`,
                    borderLeft: `4px solid ${accent}`,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px 12px',
                      alignItems: 'center',
                      marginBottom: 8,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: monoFont,
                        fontSize: 10,
                        letterSpacing: '0.12em',
                        textTransform: 'uppercase',
                        color: agent ? '#fff' : accent,
                        fontWeight: 700,
                        padding: '4px 10px',
                        borderRadius: agent ? 6 : 999,
                        background: agent ? accent : `${accent}18`,
                      }}
                    >
                      {ACTOR_LABELS[entry.actor]}
                    </span>
                    <span
                      style={{
                        fontFamily: monoFont,
                        fontSize: 11,
                        color: MUTED,
                        fontWeight: 500,
                      }}
                    >
                      {formatTimestamp(entry.at)}
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: 16,
                      fontWeight: 600,
                      color: NAVY,
                      margin: '0 0 4px',
                      lineHeight: 1.35,
                      letterSpacing: '-0.01em',
                    }}
                  >
                    {actionLabel(entry.action)}
                  </p>
                  {entry.detail && (
                    <p
                      style={{
                        fontSize: 14,
                        color: '#4a4a78',
                        margin: 0,
                        lineHeight: 1.55,
                        fontFamily: sansFont,
                      }}
                    >
                      <LinkifiedText text={entry.detail} />
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

function LegendDot({
  color,
  square,
  label,
}: {
  color: string
  square: boolean
  label: string
}) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontFamily: monoFont,
        fontSize: 10,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: MUTED,
        fontWeight: 600,
      }}
    >
      <span
        aria-hidden
        style={{
          width: 12,
          height: 12,
          borderRadius: square ? 3 : 999,
          background: color,
        }}
      />
      {label}
    </span>
  )
}
