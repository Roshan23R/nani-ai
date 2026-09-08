'use client'

import type { EpisodeError } from '../types'
import { CARE_HOME } from '../routes'
import MonoButton from '../../renderer/src/components/ui/MonoButton'
import SectionLabel from '../../renderer/src/components/ui/SectionLabel'
import { TextLink } from './TextLink'
import { cardStyle, MUTED, NAVY, monoFont, sansFont } from '../ui'
import { AlertTriangle } from 'lucide-react'

export default function ErrorPanel({
  error,
  onRetry,
  retrying,
}: {
  error: EpisodeError
  onRetry?: () => void
  retrying?: boolean
}) {
  return (
    <section
      style={{
        ...cardStyle,
        border: '1px solid #f0c8c8',
        background: 'linear-gradient(165deg, #fffafa 0%, #fff 55%)',
        padding: '28px 28px 26px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 16 }}>
        <div
          aria-hidden
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: '#fdeaea',
            border: '1px solid #f0c0c0',
            display: 'grid',
            placeItems: 'center',
            color: '#c83030',
            flexShrink: 0,
          }}
        >
          <AlertTriangle size={22} strokeWidth={2.2} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <SectionLabel>Needs your attention</SectionLabel>
          <p
            style={{
              fontSize: 20,
              fontWeight: 600,
              color: NAVY,
              margin: '0 0 8px',
              fontFamily: sansFont,
              letterSpacing: '-0.02em',
              lineHeight: 1.3,
            }}
          >
            {error.message}
          </p>
          <p style={{ fontSize: 15, lineHeight: 1.55, color: '#4a4a78', margin: 0 }}>
            {error.action_hint ||
              'NaniAi could not continue automatically. Retry with the same file, or upload a clearer prescription.'}
          </p>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          alignItems: 'center',
          paddingTop: 4,
        }}
      >
        {error.retryable && onRetry ? (
          <MonoButton onClick={onRetry} disabled={retrying} variant="danger">
            {retrying ? 'Retrying…' : 'Try again'}
          </MonoButton>
        ) : null}
        <TextLink
          href={`${CARE_HOME}#upload-episode`}
          style={{
            fontFamily: monoFont,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
          }}
        >
          Upload a clearer photo →
        </TextLink>
      </div>

      {!error.retryable && (
        <p style={{ fontFamily: monoFont, fontSize: 10, color: MUTED, margin: '16px 0 0' }}>
          This step cannot be retried automatically. Upload a new prescription or contact support.
        </p>
      )}
    </section>
  )
}
