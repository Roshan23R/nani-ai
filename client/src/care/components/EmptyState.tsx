'use client'

import type { ReactNode } from 'react'
import { MUTED, NAVY, monoFont, sansFont } from '../ui'

type EmptyStateProps = {
  title: string
  body?: string
  icon?: ReactNode
  action?: ReactNode
  /** block = padded panel · compact = tight inline */
  variant?: 'block' | 'compact'
}

/** Shared empty / waiting copy so blank panels never look broken. */
export default function EmptyState({
  title,
  body,
  icon,
  action,
  variant = 'block',
}: EmptyStateProps) {
  const pad = variant === 'compact' ? '20px 16px' : '36px 24px'
  return (
    <div
      role="status"
      style={{
        padding: pad,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        gap: 10,
        fontFamily: sansFont,
        minHeight: variant === 'block' ? 120 : undefined,
      }}
    >
      {icon ? (
        <span style={{ color: MUTED, opacity: 0.7, display: 'flex', marginBottom: 2 }}>{icon}</span>
      ) : null}
      <p
        style={{
          margin: 0,
          fontSize: 15,
          fontWeight: 600,
          color: NAVY,
          lineHeight: 1.4,
        }}
      >
        {title}
      </p>
      {body ? (
        <p
          style={{
            margin: 0,
            fontSize: 13,
            color: MUTED,
            lineHeight: 1.55,
            maxWidth: 340,
          }}
        >
          {body}
        </p>
      ) : null}
      {action ? (
        <div style={{ marginTop: 8, fontFamily: monoFont, fontSize: 10 }}>{action}</div>
      ) : null}
    </div>
  )
}
