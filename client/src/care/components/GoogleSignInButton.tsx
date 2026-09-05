'use client'

import { useEffect, useRef, useState } from 'react'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential?: string }) => void
          }) => void
          renderButton: (parent: HTMLElement, options: { theme: 'outline'; size: 'large'; width: number }) => void
        }
      }
    }
  }
}

type GoogleSignInButtonProps = {
  onCredential: (credential: string) => Promise<void>
}

const SCRIPT_ID = 'google-identity-services'

export default function GoogleSignInButton({ onCredential }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID
  console.log(`Google OAuth client ID: ${clientId}`)
  useEffect(() => {
    if (!clientId || !containerRef.current) return

    const render = () => {
      if (!window.google || !containerRef.current) return
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: ({ credential }) => {
          if (!credential) {
            setError('Google did not return a sign-in credential.')
            return
          }
          void onCredential(credential).catch(() => {
            setError('We could not sign you in with Google. Please try again.')
          })
        },
      })
      containerRef.current.replaceChildren()
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: 'outline',
        size: 'large',
        width: Math.min(360, Math.max(260, containerRef.current.clientWidth)),
      })
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
    document.head.appendChild(script)
  }, [clientId, onCredential])

  if (!clientId) {
    return <p style={{ margin: 0, color: '#8a3c3c', fontSize: 13 }}>Google sign-in is not configured.</p>
  }

  return (
    <div style={{ display: 'grid', justifyItems: 'center', gap: 10 }}>
      <div ref={containerRef} aria-label="Sign in with Google" />
      {error ? <p role="alert" style={{ margin: 0, color: '#8a3c3c', fontSize: 13 }}>{error}</p> : null}
    </div>
  )
}