'use client'

import type { Lab } from '../types'
import SectionLabel from '../../renderer/src/components/ui/SectionLabel'
import EmptyState from './EmptyState'
import CareLoader from './CareLoader'
import { BLUE, cardStyle, MUTED, NAVY, TEAL, monoFont } from '../ui'
import { ExternalLink, mapsUrl } from './TextLink'
import { FlaskConical } from 'lucide-react'

export default function LabsCard({ labs, searching = false }: { labs: Lab[]; searching?: boolean }) {
  return (
    <section style={cardStyle}>
      <SectionLabel>Labs</SectionLabel>
      <p style={{ fontSize: 13, color: MUTED, margin: '0 0 16px', lineHeight: 1.55 }}>
        Nearby labs NaniAi shortlisted — the selected one is highlighted.
      </p>
      {!labs.length ? (
        searching ? (
          <CareLoader variant="block" label="Searching nearby labs…" minHeight={120} />
        ) : (
          <EmptyState
            icon={<FlaskConical size={26} strokeWidth={1.75} />}
            title="No labs shortlisted yet"
            body="Once tests are confirmed, NaniAi finds nearby diagnostics centres here."
          />
        )
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {labs.map((lab) => (
            <div
              key={lab.place_id}
              style={{
                padding: '14px 16px',
                borderRadius: 6,
                border: lab.selected ? `2px solid ${BLUE}` : '1px solid #e0e0f0',
                background: lab.selected ? `${BLUE}08` : '#fff',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <div>
                  <p style={{ fontSize: 15, fontWeight: 600, color: NAVY, margin: '0 0 4px' }}>{lab.name}</p>
                  <ExternalLink
                    href={mapsUrl(lab.address)}
                    style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 0 }}
                  >
                    {lab.address}
                  </ExternalLink>
                  {lab.open_now != null && (
                    <p style={{ fontFamily: monoFont, fontSize: 10, color: lab.open_now ? TEAL : MUTED, margin: '6px 0 0' }}>
                      {lab.open_now ? 'Open now' : 'Closed now'}
                    </p>
                  )}
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <p style={{ fontFamily: monoFont, fontSize: 11, color: TEAL, margin: 0 }}>{lab.distance_km} km</p>
                  <p style={{ fontFamily: monoFont, fontSize: 10, color: MUTED, margin: '4px 0 0' }}>
                    ★ {lab.rating}
                  </p>
                </div>
              </div>
              {lab.selected && lab.selection_reason && (
                <p
                  style={{
                    margin: '12px 0 0',
                    padding: '10px 12px',
                    background: '#fff',
                    borderRadius: 4,
                    border: '1px solid #e0e0f0',
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: '#4a4a78',
                  }}
                >
                  <span style={{ fontFamily: monoFont, fontSize: 9, letterSpacing: '0.1em', color: BLUE, display: 'block', marginBottom: 4 }}>
                    WHY THIS LAB
                  </span>
                  {lab.selection_reason}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
