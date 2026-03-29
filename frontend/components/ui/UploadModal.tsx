"use client"

import { useRef, useState } from "react"
import { api } from "@/lib/api"
import type { IngestResponse } from "@/lib/types"

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [successCount, setSuccessCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function resetState() {
    setFile(null)
    setLoading(false)
    setSuccessCount(null)
    setError(null)
    setDragging(false)
  }

  function handleClose() {
    resetState()
    onClose()
  }

  function pickFile(picked: File) {
    setFile(picked)
    setError(null)
    setSuccessCount(null)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const picked = e.dataTransfer.files[0]
    if (picked) pickFile(picked)
  }

  async function handleUpload() {
    if (!file) return
    setLoading(true)
    setError(null)

    const ext = file.name.split(".").pop()?.toLowerCase()
    const endpoint =
      ext === "xlsx" ? "/api/v1/ingest/xlsx" : "/api/v1/ingest/csv"

    const formData = new FormData()
    formData.append("file", file)

    try {
      const { data } = await api.post<IngestResponse>(
        `${endpoint}?feed_source=auto`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      )
      setSuccessCount(data.products_imported ?? null)
      onSuccess()
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Uppladdningen misslyckades."
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md bg-surface-container-lowest rounded-xl border border-outline-variant shadow-2xl p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-headline text-lg font-bold text-on-surface">
            Ladda upp produktfeed
          </h2>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-[20px] text-on-surface-variant">
              close
            </span>
          </button>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
            dragging
              ? "border-primary bg-primary/5"
              : "border-outline-variant hover:border-primary hover:bg-surface-container-low"
          }`}
        >
          <span className="material-symbols-outlined text-[40px] text-on-surface-variant">
            upload_file
          </span>
          <div className="text-center">
            <p className="text-sm font-medium text-on-surface">
              Dra och släpp fil här
            </p>
            <p className="text-xs text-on-surface-variant mt-1">
              eller klicka för att välja — .csv eller .xlsx
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            className="hidden"
            onChange={(e) => {
              const picked = e.target.files?.[0]
              if (picked) pickFile(picked)
            }}
          />
        </div>

        {/* Selected file */}
        {file && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg">
            <span className="material-symbols-outlined text-[16px] text-primary">
              description
            </span>
            <span className="text-xs text-on-surface truncate flex-1">
              {file.name}
            </span>
            <button
              onClick={() => setFile(null)}
              className="text-on-surface-variant hover:text-error transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        )}

        {/* Success */}
        {successCount !== null && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-[#dcf5e8] rounded-lg">
            <span className="material-symbols-outlined text-[16px] text-[#1a7f4b]">
              check_circle
            </span>
            <span className="text-xs text-[#1a7f4b] font-medium">
              {successCount} produkter importerade
            </span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-error-container rounded-lg">
            <span className="material-symbols-outlined text-[16px] text-on-error-container">
              error
            </span>
            <span className="text-xs text-on-error-container">{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium rounded-xl border border-outline-variant text-on-surface hover:bg-surface-container transition-colors"
          >
            Avbryt
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl bg-primary text-white hover:bg-primary-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined text-[16px] animate-spin">
                  progress_activity
                </span>
                Laddar upp...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[16px]">upload</span>
                Ladda upp
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
