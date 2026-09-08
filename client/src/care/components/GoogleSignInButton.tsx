'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { BLUE, MUTED, monoFont, sansFont } from '../ui'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential?: string }) => void
            auto_select?: boolean
            cancel_on_tap_outside?: boolean
          }) => void
          renderButton: (
            parent: HTMLElement,
            options: {
              theme: 'outline' | 'filled_blue'
              size: 'large' | 'medium'
              width: number
              text?: 'signin_with' | 'continue_with'
              shape?: 'rectangular' | 'pill'
              logo_alignment?: 'left' | 'center'
            },
          ) => void
        }
      }
    }
  }
}

type GoogleSignInButtonProps = {
  onCredential: (credential: string) => Promise<void>
}

const SCRIPT_ID = 'google-identity-services'

function GoogleMark({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden>
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  )
}

export default function GoogleSignInButton({ onCredential }: GoogleSignInButtonProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const gisRef = useRef<HTMLDivElement>(null)
  const onCredentialRef = useRef(onCredential)
  const [error, setError] = useState('')
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID

  useEffect(() => {
    onCredentialRef.current = onCredential
  }, [onCredential])

  useEffect(() => {
    if (!clientId || !gisRef.current || !wrapRef.current) return

    const render = () => {
      if (!window.google || !gisRef.current || !wrapRef.current) return
      const width = Math.max(280, Math.round(wrapRef.current.getBoundingClientRect().width))

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: ({ credential }) => {
          if (!credential) {
            setError('Google did not return a sign-in credential.')
            setBusy(false)
            return
          }
          setBusy(true)
          setError('')
          void onCredentialRef
            .current(credential)
            .catch(() => {
              setError('We could not sign you in with Google. Please try again.')
            })
            .finally(() => setBusy(false))
        },
      })

      gisRef.current.replaceChildren()
      window.google.accounts.id.renderButton(gisRef.current, {
        theme: 'outline',
        size: 'large',
        width,
        text: 'continue_with',
        shape: 'rectangular',
        logo_alignment: 'left',
      })

      // Stretch the GIS iframe to cover our themed button so clicks hit Google.
      const iframe = gisRef.current.querySelector('iframe')
      const btn = gisRef.current.querySelector('div[role="button"]') as HTMLElement | null
      if (iframe) {
        Object.assign((iframe as HTMLElement).style, {
          position: 'absolute',
          inset: '0',
          width: '100%',
          height: '100%',
          opacity: '0.001',
          cursor: 'pointer',
        })
      }
      if (btn) {
        Object.assign(btn.style, {
          position: 'absolute',
          inset: '0',
          width: '100%',
          height: '100%',
          margin: '0',
          opacity: '0.001',
        })
      }
      setReady(true)
    }

    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null
    if (existing) {
      if (window.google) render()
      else existing.addEventListener('load', render, { once: true })
      return
    }

    const script = document.createElement('script')
    script.id = SCRIPT_ID
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.onload = render
    script.onerror = () => setError('Could not load Google sign-in. Check your network and try again.')
    document.head.appendChild(script)
  }, [clientId])

  if (!clientId) {
    return (
      <p role="alert" style={{ margin: 0, color: '#8a3c3c', fontSize: 13, lineHeight: 1.5 }}>
        Google sign-in is not configured. Set{' '}
        <code style={{ fontFamily: monoFont, fontSize: 11 }}>NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID</code> and
        rebuild.
      </p>
    )
  }

  return (
    <div style={{ display: 'grid', justifyItems: 'stretch', gap: 12, width: '100%' }}>
      <div ref={wrapRef} style={{ position: 'relative', width: '100%' }}>
        <motion.div
          aria-hidden
          animate={busy ? { opacity: 0.55 } : { opacity: 1 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            width: '100%',
            padding: '14px 22px',
            background: BLUE,
            color: '#fff',
            borderRadius: 8,
            fontFamily: monoFont,
            fontWeight: 700,
            fontSize: 11,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            boxShadow: '0 10px 28px rgba(26, 26, 232, 0.28)',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        >
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: '#fff',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            <GoogleMark size={16} />
          </span>
          <span>{busy ? 'Signing in…' : ready ? 'Continue with Google' : 'Loading Google…'}</span>
        </motion.div>

        {/* Invisible official GIS button — receives the real click */}
        <div
          ref={gisRef}
          aria-label="Continue with Google"
          style={{
            position: 'absolute',
            inset: 0,
            overflow: 'hidden',
            opacity: busy ? 0 : 1,
            pointerEvents: busy ? 'none' : 'auto',
            borderRadius: 8,
            cursor: ready ? 'pointer' : 'wait',
          }}
        />
      </div>

      <p
        style={{
          margin: 0,
          textAlign: 'center',
          fontFamily: sansFont,
          fontSize: 12,
          color: MUTED,
          lineHeight: 1.45,
        }}
      >
        Uses your Google account to identify this care record.
      </p>

      {error ? (
        <p
          role="alert"
          style={{
            margin: 0,
            color: '#8a3c3c',
            fontSize: 13,
            lineHeight: 1.45,
            textAlign: 'center',
            fontFamily: sansFont,
          }}
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}
