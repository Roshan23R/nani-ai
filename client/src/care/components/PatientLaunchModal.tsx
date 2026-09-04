'use client'

import { useEffect, useId } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import GoogleSignInButton from './GoogleSignInButton'
import { LIGHT_BLUE, NAVY, TEAL, monoFont, sansFont } from '../ui'
import { signInWithGoogle } from '../api'
import { usePatient } from '../context/PatientContext'
import NaniLogo from '../../renderer/src/components/NaniLogo'

type PatientLaunchModalProps = {
  open: boolean
  onClose: () => void
  onLaunch: () => void
}

export default function PatientLaunchModal({ open, onClose, onLaunch }: PatientLaunchModalProps) {
  const titleId = useId()
  const { setGooglePatient } = usePatient()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const handleCredential = async (credential: string) => {
    const user = await signInWithGoogle(credential)
    setGooglePatient(user)
    onLaunch()
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 200,
            background: 'rgba(10, 10, 92, 0.42)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
            fontFamily: sansFont,
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              maxWidth: 440,
              background: '#fff',
              borderRadius: 14,
              border: '1px solid #e0e0f0',
              boxShadow: '0 28px 80px rgba(10, 10, 92, 0.22)',
              overflow: 'hidden',
            }}
          >
            <div style={{ height: 3, background: TEAL }} />
            <div style={{ padding: '28px 28px 20px', background: LIGHT_BLUE }}>
              <NaniLogo size={44} textSize={16} href={false} />
              <h2
                id={titleId}
                style={{
                  fontSize: 24,
                  fontWeight: 300,
                  letterSpacing: '-0.02em',
                  color: NAVY,
                  margin: '18px 0 8px',
                }}
              >
                Continue with <strong style={{ fontWeight: 600 }}>Google</strong>
              </h2>
              <p style={{ fontSize: 14, lineHeight: 1.55, color: '#4a4a78', margin: 0 }}>
                Your verified Google email identifies your care record, and your Google profile name is used in the app.
              </p>
            </div>

            <div style={{ padding: '20px 28px 28px' }}>
              <GoogleSignInButton onCredential={handleCredential} />

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  marginTop: 22,
                  flexWrap: 'wrap',
                }}
              >
                <button
                  type="button"
                  onClick={onClose}
                  style={{
                    padding: '11px 16px',
                    borderRadius: 8,
                    border: '1px solid #e0e0f0',
                    background: '#fff',
                    color: NAVY,
                    fontFamily: monoFont,
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.12em',
                    textTransform: 'uppercase',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
