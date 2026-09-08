'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  loadPatientProfileRemote,
  upsertPatientProfile,
  listPatients,
  type GoogleUser,
} from '../api'
import { DEFAULT_PATIENT_ID, MOCK_PATIENTS } from '../patients'
import {
  getPatientProfile,
  localToRemotePayload,
  prefillPatientProfileFromGoogle,
} from '../patientProfileStorage'
import type { Patient } from '../types'

const STORAGE_KEY = 'naniai.patient_id'
const GOOGLE_USER_KEY = 'naniai.google_user'

interface PatientContextType {
  patients: Patient[]
  patientId: string
  selectedPatient: Patient | undefined
  googleUser: GoogleUser | null
  setPatientId: (patientId: string) => void
  setGooglePatient: (user: GoogleUser) => void
  hydrated: boolean
  loading: boolean
}

const PatientContext = createContext<PatientContextType | null>(null)

function readStoredPatientId(): string {
  if (typeof window === 'undefined') return DEFAULT_PATIENT_ID
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_PATIENT_ID
  } catch {
    return DEFAULT_PATIENT_ID
  }
}

function writeStoredPatientId(patientId: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, patientId)
}

function readStoredGoogleUser(): GoogleUser | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(GOOGLE_USER_KEY)
    if (!raw) return null
    return JSON.parse(raw) as GoogleUser
  } catch {
    return null
  }
}

function writeStoredGoogleUser(user: GoogleUser | null) {
  if (typeof window === 'undefined') return
  if (!user) {
    window.localStorage.removeItem(GOOGLE_USER_KEY)
    return
  }
  window.localStorage.setItem(GOOGLE_USER_KEY, JSON.stringify(user))
}

function googleAsPatient(user: GoogleUser): Patient {
  return {
    patient_id: user.patient_id,
    name: user.name,
    city: '',
    scenario: user.email ? `Google · ${user.email}` : 'Google account',
  }
}

export function PatientProvider({ children }: { children: ReactNode }) {
  const [patients, setPatients] = useState<Patient[]>(MOCK_PATIENTS)
  const [patientId, setPatientIdState] = useState(DEFAULT_PATIENT_ID)
  const [googleUser, setGoogleUserState] = useState<GoogleUser | null>(null)
  const [hydrated, setHydrated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const storedId = readStoredPatientId()
    const google = readStoredGoogleUser()
    setPatientIdState(storedId)
    if (google) {
      setGoogleUserState(google)
      const existing = getPatientProfile(google.patient_id)
      if (!existing?.displayName?.trim() || !existing?.email?.trim()) {
        prefillPatientProfileFromGoogle(google)
      }
      setPatients((current) => {
        const asPatient = googleAsPatient(google)
        return [asPatient, ...current.filter((item) => item.patient_id !== asPatient.patient_id)]
      })
      // Hydrate from API into local cache when online.
      void loadPatientProfileRemote(google.patient_id, googleAsPatient(google))
    }
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    let cancelled = false
    void (async () => {
      try {
        const list = await listPatients()
        if (cancelled || !list.length) return
        const google = readStoredGoogleUser()
        setPatients(() => {
          if (!google) return list
          const asPatient = googleAsPatient(google)
          return [asPatient, ...list.filter((item) => item.patient_id !== asPatient.patient_id)]
        })
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [hydrated])

  const setPatientId = useCallback((nextId: string) => {
    setPatientIdState(nextId)
    writeStoredPatientId(nextId)
  }, [])

  const setGooglePatient = useCallback((user: GoogleUser) => {
    const patient = googleAsPatient(user)
    writeStoredGoogleUser(user)
    const local = prefillPatientProfileFromGoogle(user)
    setGoogleUserState(user)
    setPatients((current) => [patient, ...current.filter((item) => item.patient_id !== user.patient_id)])
    setPatientIdState(user.patient_id)
    writeStoredPatientId(user.patient_id)
    // Persist identity to Dynamo via PUT /api/patients/{id}
    void upsertPatientProfile(
      user.patient_id,
      localToRemotePayload(local, { scenario: patient.scenario, city: patient.city }),
    )
  }, [])

  const selectedPatient = useMemo(
    () => patients.find((p) => p.patient_id === patientId) ?? patients[0],
    [patients, patientId],
  )

  return (
    <PatientContext.Provider
      value={{
        patients,
        patientId,
        selectedPatient,
        googleUser,
        setPatientId,
        setGooglePatient,
        hydrated,
        loading,
      }}
    >
      {children}
    </PatientContext.Provider>
  )
}

export function usePatient() {
  const context = useContext(PatientContext)
  if (!context) {
    throw new Error('usePatient must be used within PatientProvider')
  }
  return context
}
