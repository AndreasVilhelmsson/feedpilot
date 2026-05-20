"use client"

import type { PreflightResponse } from "@/lib/types"

interface PreflightModalProps {
  isOpen: boolean
  preflight: PreflightResponse | null
  onConfirm: () => void
  onCancel: () => void
}

export function PreflightModal({ isOpen, preflight, onConfirm, onCancel }: PreflightModalProps) {
  if (!isOpen || !preflight) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md bg-surface-container-lowest rounded-xl border border-outline-variant shadow-2xl p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-headline text-lg font-bold text-on-surface">
            Bekräfta enrichment
          </h2>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-[20px] text-on-surface-variant">
              close
            </span>
          </button>
        </div>

        {/* Key metrics */}
        <div className="flex flex-col gap-3 mb-5">
          <div className="flex items-center justify-between px-4 py-3 bg-surface-container rounded-xl">
            <span className="text-sm text-on-surface-variant">Produkter</span>
            <span className="text-sm font-medium text-on-surface">
              {preflight.product_count} produkter
            </span>
          </div>
          <div className="flex items-center justify-between px-4 py-3 bg-surface-container rounded-xl">
            <span className="text-sm text-on-surface-variant">Estimerade tokens</span>
            <span className="text-sm font-medium text-on-surface">
              {preflight.estimated_total_tokens.toLocaleString("sv-SE")} tokens
            </span>
          </div>
          <div className="flex items-center justify-between px-4 py-3 bg-surface-container rounded-xl">
            <span className="text-sm text-on-surface-variant">Estimerad kostnad</span>
            <span className="text-sm font-medium text-on-surface">
              ${preflight.estimated_cost_usd}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium rounded-xl border border-outline-variant text-on-surface hover:bg-surface-container transition-colors"
          >
            Avbryt
          </button>
          <button
            onClick={onConfirm}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl bg-primary text-white hover:bg-primary-container transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">check</span>
            Bekräfta
          </button>
        </div>
      </div>
    </div>
  )
}
