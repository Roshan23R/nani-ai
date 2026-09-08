'use client'

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Check, Trash2 } from 'lucide-react'
import type { ConfirmationTest, Prescription, PrescriptionTest } from '../types'
import MonoButton from '../../renderer/src/components/ui/MonoButton'
import SectionLabel from '../../renderer/src/components/ui/SectionLabel'
import { BLUE, MUTED, NAVY, TEAL, cardStyle, monoFont, sansFont } from '../ui'

type EditableRow = ConfirmationTest & { rowId: string }

function toRows(tests: PrescriptionTest[]): EditableRow[] {
  return tests.map((t, i) => ({
    ...t,
    keep: true,
    rowId: `${t.test_code}-${i}`,
  }))
}

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p
        style={{
          fontFamily: monoFont,
          fontSize: 9,
          letterSpacing: '0.12em',
          color: MUTED,
          textTransform: 'uppercase',
          margin: '0 0 4px',
        }}
      >
        {label}
      </p>
      <p style={{ fontSize: 14, color: NAVY, margin: 0, lineHeight: 1.4 }}>{value}</p>
    </div>
  )
}

export default function ConfirmationPanel({
  prescription,
  extractedTests,
  submitting,
  onConfirm,
  onReupload,
}: {
  prescription: Prescription | null
  extractedTests: PrescriptionTest[]
  submitting?: boolean
  onConfirm: (tests: ConfirmationTest[]) => void | Promise<void>
  onReupload: () => void
}) {
  const seed = extractedTests.length
    ? extractedTests
    : (prescription?.tests ?? [])
  const [rows, setRows] = useState<EditableRow[]>(() => toRows(seed))

  useEffect(() => {
    setRows(toRows(seed))
    // Reset when the episode's extracted list changes identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(seed)])

  const keptCount = useMemo(() => rows.filter((r) => r.keep !== false).length, [rows])
  const imageUrl = prescription?.source_file_url

  const updateRow = (rowId: string, patch: Partial<EditableRow>) => {
    setRows((prev) => prev.map((r) => (r.rowId === rowId ? { ...r, ...patch } : r)))
  }

  const removeRow = (rowId: string) => {
    setRows((prev) =>
      prev.map((r) => (r.rowId === rowId ? { ...r, keep: false } : r)),
    )
  }

  const restoreRow = (rowId: string) => {
    setRows((prev) =>
      prev.map((r) => (r.rowId === rowId ? { ...r, keep: true } : r)),
    )
  }

  const handleConfirm = () => {
    if (keptCount < 1 || submitting) return
    void onConfirm(
      rows.map(({ test_code, display_name, urgency, keep }) => ({
        test_code,
        display_name,
        urgency,
        keep: keep !== false,
      })),
    )
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      style={{ ...cardStyle, padding: 0, overflow: 'hidden', fontFamily: sansFont }}
    >
      <div
        style={{
          padding: '18px 22px 14px',
          borderBottom: '1px solid #eeeef6',
          background: 'linear-gradient(180deg, #fafafe 0%, #fff 100%)',
        }}
      >
        <SectionLabel>Confirm what we read</SectionLabel>
        <p style={{ margin: '8px 0 0', fontSize: 14, color: '#4a4a78', lineHeight: 1.55, maxWidth: 520 }}>
          Compare each test with the prescription. Edit names, toggle urgency, or remove
          anything that was misread — then we find labs.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.05fr) minmax(0, 1fr)',
          gap: 0,
        }}
        className="confirm-grid"
      >
        <div
          style={{
            padding: '18px 20px 22px',
            borderRight: '1px solid #eeeef6',
            background: '#f7f7fb',
            minHeight: 360,
          }}
        >
          <p
            style={{
              fontFamily: monoFont,
              fontSize: 9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: MUTED,
              margin: '0 0 12px',
              fontWeight: 600,
            }}
          >
            Your prescription
          </p>
          {imageUrl ? (
            <div
              style={{
                borderRadius: 12,
                overflow: 'hidden',
                border: '1px solid #e4e4f0',
                background: '#fff',
                boxShadow: '0 8px 28px rgba(10,10,92,0.06)',
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt="Uploaded prescription"
                style={{
                  display: 'block',
                  width: '100%',
                  height: 'auto',
                  maxHeight: 520,
                  objectFit: 'contain',
                  background: '#fffdf8',
                }}
              />
            </div>
          ) : (
            <div
              style={{
                borderRadius: 12,
                border: '1px dashed #d8d8e8',
                padding: 32,
                textAlign: 'center',
                color: MUTED,
                fontSize: 13,
                background: '#fff',
              }}
            >
              Prescription image unavailable — check the test list carefully against your paper copy.
            </div>
          )}
        </div>

        <div style={{ padding: '18px 20px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {(prescription?.patient ||
            prescription?.complaint ||
            prescription?.diagnosis ||
            (prescription?.medicines?.length ?? 0) > 0) && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 14,
                padding: '12px 14px',
                borderRadius: 10,
                background: '#f8f8fc',
                border: '1px solid #eeeef6',
              }}
            >
              {prescription?.patient ? (
                <MetaChip label="Patient" value={prescription.patient} />
              ) : null}
              {prescription?.diagnosis ? (
                <MetaChip label="Diagnosis" value={prescription.diagnosis} />
              ) : null}
              {prescription?.complaint ? (
                <MetaChip label="Complaint" value={prescription.complaint} />
              ) : null}
              {prescription?.doctor ? (
                <MetaChip label="Prescriber" value={prescription.doctor} />
              ) : null}
              {(prescription?.medicines?.length ?? 0) > 0 ? (
                <div style={{ gridColumn: '1 / -1' }}>
                  <p
                    style={{
                      fontFamily: monoFont,
                      fontSize: 9,
                      letterSpacing: '0.12em',
                      color: MUTED,
                      textTransform: 'uppercase',
                      margin: '0 0 4px',
                    }}
                  >
                    Medicines
                  </p>
                  <p style={{ fontSize: 13, color: '#4a4a78', margin: 0, lineHeight: 1.5 }}>
                    {prescription!.medicines.map((m) => `${m.name} ${m.dose}`).join(' · ')}
                  </p>
                </div>
              ) : null}
            </div>
          )}

          <div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 10,
              }}
            >
              <p
                style={{
                  fontFamily: monoFont,
                  fontSize: 9,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  color: MUTED,
                  margin: 0,
                  fontWeight: 600,
                }}
              >
                Tests to book
              </p>
              <span style={{ fontFamily: monoFont, fontSize: 10, color: MUTED }}>
                {keptCount} kept
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rows.map((row) => {
                const removed = row.keep === false
                return (
                  <div
                    key={row.rowId}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr auto auto',
                      gap: 8,
                      alignItems: 'center',
                      padding: '10px 12px',
                      borderRadius: 10,
                      border: `1px solid ${removed ? '#f0d0d0' : '#e4e4f0'}`,
                      background: removed ? '#fff8f8' : '#fafafe',
                      opacity: removed ? 0.72 : 1,
                    }}
                  >
                    <input
                      type="text"
                      value={row.display_name}
                      disabled={removed || submitting}
                      onChange={(e) => updateRow(row.rowId, { display_name: e.target.value })}
                      aria-label={`Test name for ${row.test_code}`}
                      style={{
                        width: '100%',
                        border: 'none',
                        background: 'transparent',
                        fontSize: 14,
                        color: removed ? MUTED : NAVY,
                        textDecoration: removed ? 'line-through' : 'none',
                        fontFamily: sansFont,
                        outline: 'none',
                        padding: 0,
                      }}
                    />
                    <button
                      type="button"
                      disabled={removed || submitting}
                      onClick={() =>
                        updateRow(row.rowId, {
                          urgency: row.urgency === 'urgent' ? 'routine' : 'urgent',
                        })
                      }
                      style={{
                        fontFamily: monoFont,
                        fontSize: 9,
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                        fontWeight: 700,
                        padding: '6px 10px',
                        borderRadius: 6,
                        border: '1px solid',
                        borderColor: row.urgency === 'urgent' ? '#f0c0c0' : '#d0ecea',
                        background: row.urgency === 'urgent' ? '#fff0f0' : '#f0faf9',
                        color: row.urgency === 'urgent' ? '#c83030' : TEAL,
                        cursor: removed || submitting ? 'default' : 'pointer',
                      }}
                    >
                      {row.urgency}
                    </button>
                    {removed ? (
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => restoreRow(row.rowId)}
                        style={{
                          fontFamily: monoFont,
                          fontSize: 9,
                          letterSpacing: '0.08em',
                          textTransform: 'uppercase',
                          border: 'none',
                          background: 'transparent',
                          color: BLUE,
                          cursor: 'pointer',
                          padding: '4px 2px',
                        }}
                      >
                        Undo
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => removeRow(row.rowId)}
                        aria-label={`Remove ${row.display_name}`}
                        style={{
                          display: 'grid',
                          placeItems: 'center',
                          width: 32,
                          height: 32,
                          borderRadius: 8,
                          border: '1px solid #ececf4',
                          background: '#fff',
                          color: MUTED,
                          cursor: 'pointer',
                        }}
                      >
                        <Trash2 size={14} strokeWidth={2} />
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 10,
              marginTop: 'auto',
              paddingTop: 8,
            }}
          >
            <MonoButton
              onClick={handleConfirm}
              disabled={keptCount < 1 || !!submitting}
              variant="primary"
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Check size={13} strokeWidth={2.5} />
                {submitting ? 'Confirming…' : 'Confirm and find labs'}
              </span>
            </MonoButton>
            <MonoButton onClick={onReupload} disabled={!!submitting} variant="default">
              I need to re-upload
            </MonoButton>
          </div>
          {keptCount < 1 && (
            <p style={{ margin: 0, fontSize: 12, color: '#c83030' }}>
              Keep at least one test, or re-upload the prescription.
            </p>
          )}
        </div>
      </div>

      <style>{`
        @media (max-width: 860px) {
          .confirm-grid {
            grid-template-columns: 1fr !important;
          }
          .confirm-grid > div:first-child {
            border-right: none !important;
            border-bottom: 1px solid #eeeef6;
          }
        }
      `}</style>
    </motion.section>
  )
}
