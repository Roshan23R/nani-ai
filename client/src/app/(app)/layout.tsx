'use client'

import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import MainLayout from '../../renderer/src/components/MainLayout'
import { useProfile, profileFromName } from '../../renderer/src/context/ProfileContext'
import { usePatient } from '../../care/context/PatientContext'
import { getPatientProfile } from '../../care/patientProfileStorage'
import { resolveAvatarUrl } from '../../lib/notionAvatars'
import AppLoader from '../../components/AppLoader'

export default function AppShellLayout({ children }: { children: ReactNode }) {
  const { profile, setProfile } = useProfile()
  const { selectedPatient, googleUser, hydrated, loading } = usePatient()
  const router = useRouter()
  const [allowed, setAllowed] = useState(false)

  useEffect(() => {
    if (!hydrated || loading) return

    if (!selectedPatient) {
      setAllowed(false)
      router.replace('/')
      return
    }

    const local = getPatientProfile(selectedPatient.patient_id)
    const name = local?.displayName?.trim() || selectedPatient.name
    const avatarUrl = resolveAvatarUrl(
      name,
      googleUser?.patient_id === selectedPatient.patient_id
        ? googleUser.picture || local?.avatarUrl
        : local?.avatarUrl,
    )

    const needsUpdate =
      !profile ||
      profile.name !== name ||
      (avatarUrl && profile.avatarUrl !== avatarUrl)

    if (needsUpdate) {
      setProfile({
        ...profileFromName(name, profile),
        avatarUrl,
      })
    }
    setAllowed(true)
  }, [hydrated, loading, selectedPatient, googleUser, profile, router, setProfile])

  if (!hydrated || loading || !allowed || !selectedPatient) {
    return (
      <AppLoader
        label={hydrated ? 'Opening your care space…' : 'Loading profiles…'}
        detail="Getting your episodes ready"
      />
    )
  }

  return <MainLayout profile={profile ?? undefined}>{children}</MainLayout>
}
