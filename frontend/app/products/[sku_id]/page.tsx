"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter, useParams } from "next/navigation"
import { api } from "@/lib/api"
import type {
  ProductDetailResponse,
  EnrichmentDetail,
  EnrichResponse,
  ImageAnalysisResult,
} from "@/lib/types"

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreClass(score: number): string {
  if (score >= 80) return "border-[#1a7f4b] text-[#1a7f4b]"
  if (score >= 50) return "border-tertiary-fixed-dim text-tertiary"
  return "border-error text-error"
}

function confidencePill(confidence: number) {
  const pct = Math.round(confidence * 100)
  const cls =
    pct >= 90
      ? "bg-emerald-100 text-emerald-700"
      : pct >= 70
      ? "bg-blue-100 text-blue-700"
      : "bg-amber-100 text-amber-700"
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide whitespace-nowrap ${cls}`}>
      {pct}% confidence
    </span>
  )
}

function getCurrentValue(field: string, product: ProductDetailResponse): string {
  const map: Record<string, string | null | undefined> = {
    title: product.title,
    description: product.description,
    category: product.category,
    brand: product.brand,
    price: product.price != null ? String(product.price) : null,
  }
  if (field in map) return map[field] ?? "—"
  const attrVal = (product.attributes as Record<string, unknown>)[field]
  if (attrVal != null) return String(attrVal)
  return "—"
}

function scoreLabel(score: number): { text: string; color: string } {
  if (score >= 80) return { text: "Excellent", color: "text-emerald-700" }
  if (score >= 60) return { text: "Good", color: "text-blue-700" }
  if (score >= 40) return { text: "Needs improvement", color: "text-amber-700" }
  return { text: "Poor", color: "text-error" }
}

function scoreBorderColor(score: number): string {
  if (score >= 80) return "border-emerald-500"
  if (score >= 60) return "border-blue-500"
  if (score >= 40) return "border-amber-500"
  return "border-error"
}

function riskConfig(risk: string | null) {
  if (risk === "high")
    return {
      label: "High risk",
      className: "bg-error-container text-on-error-container",
      icon: "warning",
    }
  if (risk === "medium")
    return { label: "Medium risk", className: "bg-[#fff3cd] text-[#856404]", icon: "info" }
  return { label: "Low risk", className: "bg-[#dcf5e8] text-[#1a7f4b]", icon: "check_circle" }
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="grid grid-cols-12 gap-6 mt-2">
        <div className="col-span-8 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 bg-surface-container-high rounded-xl" />
          ))}
        </div>
        <div className="col-span-4 space-y-3">
          <div className="h-28 bg-surface-container-high rounded-xl" />
          <div className="h-44 bg-surface-container-high rounded-xl" />
        </div>
      </div>
    </div>
  )
}

function EnrichmentTableRow({
  field,
  currentValue,
  decision,
  onDecide,
  editedValues,
  editingField,
  onStartEdit,
  onStopEdit,
  onCancelEdit,
  onUpdateEditedValue,
}: {
  field: EnrichmentDetail
  currentValue: string
  decision: boolean | null
  onDecide: (field: string, accepted: boolean) => void
  editedValues: Record<string, string>
  editingField: string | null
  onStartEdit: (field: string, originalValue: string) => void
  onStopEdit: () => void
  onCancelEdit: (field: string) => void
  onUpdateEditedValue: (field: string, value: string) => void
}) {
  const accepted = decision === true
  const rejected = decision === false
  const isEditing = editingField === field.field
  const displayValue = editedValues[field.field] ?? field.suggested_value
  const isModified =
    field.field in editedValues && editedValues[field.field] !== field.suggested_value

  return (
    <tr
      className={`group border-b border-outline-variant last:border-0 transition-colors ${
        accepted ? "bg-emerald-50" : rejected ? "bg-surface-container opacity-60" : ""
      }`}
    >
      {/* FÄLT */}
      <td className="px-4 py-3 align-top w-28">
        <span className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
          {field.field}
        </span>
      </td>

      {/* NUVARANDE VÄRDE */}
      <td className="px-4 py-3 align-top w-36">
        <span className="text-sm text-on-surface-variant italic line-clamp-2">
          {currentValue}
        </span>
      </td>

      {/* AI-FÖRSLAG */}
      <td className="px-4 py-3 align-top">
        {isEditing ? (
          <>
            <textarea
              className="w-full text-sm border border-primary rounded p-1 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              value={editedValues[field.field] ?? field.suggested_value}
              onChange={(e) => onUpdateEditedValue(field.field, e.target.value)}
              onBlur={onStopEdit}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  onStopEdit()
                }
                if (e.key === "Escape") onCancelEdit(field.field)
              }}
              autoFocus
              rows={field.field === "description" ? 4 : 2}
            />
            <p className="text-xs text-on-surface-variant mt-1">
              Enter för att spara · Esc för att avbryta · Shift+Enter för ny rad
            </p>
          </>
        ) : (
          <div
            className="flex items-start gap-1 cursor-text"
            onClick={() => onStartEdit(field.field, field.suggested_value)}
          >
            <p
              className={`text-sm font-medium leading-snug line-clamp-2 rounded px-1 hover:bg-primary/5 ${
                rejected
                  ? "line-through text-on-surface-variant"
                  : isModified
                  ? "text-primary italic"
                  : "text-primary"
              }`}
              title={displayValue}
            >
              {displayValue}
            </p>
            <span className="material-symbols-outlined text-xs text-on-surface-variant opacity-0 group-hover:opacity-100 mt-0.5 shrink-0">
              edit
            </span>
          </div>
        )}
      </td>

      {/* CONFIDENCE */}
      <td className="px-4 py-3 align-top w-36">
        {confidencePill(field.confidence)}
      </td>

      {/* ÅTGÄRD */}
      <td className="px-4 py-3 align-top w-20">
        {accepted ? (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700">
            <span className="material-symbols-outlined text-[16px]">check_circle</span>
            Accepted
          </span>
        ) : (
          <div className="flex items-center gap-1">
            <button
              onClick={() => onDecide(field.field, true)}
              className="w-7 h-7 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-emerald-100 hover:text-emerald-700 transition-colors"
              title="Accept"
            >
              <span className="material-symbols-outlined text-[15px]">check</span>
            </button>
            <button
              onClick={() => onDecide(field.field, false)}
              className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
                rejected
                  ? "bg-surface-container-high text-on-surface"
                  : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
              }`}
              title="Skip"
            >
              <span className="material-symbols-outlined text-[15px]">close</span>
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}

// ── ImagePanel ────────────────────────────────────────────────────────────────

function qualityBadgeClass(score: number): string {
  if (score >= 80) return "bg-emerald-500/90"
  if (score >= 60) return "bg-amber-500/90"
  return "bg-red-500/90"
}

function ImagePanel({
  skuId,
  initialImageUrl,
}: {
  skuId: string
  initialImageUrl?: string | null
}) {
  const [imageUrl, setImageUrl] = useState(initialImageUrl ?? "")
  const [imageCommitted, setImageCommitted] = useState(!!initialImageUrl)
  // Pending file for upload-then-analyze flow
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [imageAnalysis, setImageAnalysis] = useState<ImageAnalysisResult | null>(null)
  const [analyzingImage, setAnalyzingImage] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  // Sync when parent loads product data asynchronously
  useEffect(() => {
    if (initialImageUrl && !imageCommitted) {
      setImageUrl(initialImageUrl)
      setImageCommitted(true)
    }
  }, [initialImageUrl]) // eslint-disable-line react-hooks/exhaustive-deps

  // Single analyze handler — uses pendingFile for uploads, URL otherwise
  async function handleAnalyze() {
    setAnalyzingImage(true)
    setAnalysisError(null)
    try {
      let data: ImageAnalysisResult
      if (pendingFile) {
        const form = new FormData()
        form.append("file", pendingFile)
        const res = await api.post<ImageAnalysisResult>(
          `/api/v1/images/analyze-upload/${skuId}`,
          form,
          { headers: { "Content-Type": "multipart/form-data" } },
        )
        data = res.data
        setPendingFile(null)
      } else {
        const url = imageUrl.trim()
        if (!url) return
        setImageCommitted(true) // transition to LÄGE 2 before await → shows image + overlay
        const res = await api.post<ImageAnalysisResult>("/api/v1/images/analyze-url", {
          url,
          sku_id: skuId,
        })
        data = res.data
        await api.patch(`/api/v1/products/${skuId}/image`, { image_url: url })
      }
      setImageAnalysis(data)
    } catch {
      setAnalysisError(
        pendingFile ? "Bilduppladdning misslyckades." : "Bildanalys misslyckades. Kontrollera URL:en.",
      )
    } finally {
      setAnalyzingImage(false)
    }
  }

  // File picked → show preview only; analysis triggered by button click
  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ""
    if (imageUrl.startsWith("blob:")) URL.revokeObjectURL(imageUrl)
    const blobUrl = URL.createObjectURL(file)
    setImageUrl(blobUrl)
    setImageCommitted(true)
    setPendingFile(file)
    setImageAnalysis(null)
    setAnalysisError(null)
  }

  function resetToLage1() {
    if (imageUrl.startsWith("blob:")) URL.revokeObjectURL(imageUrl)
    setImageUrl("")
    setImageCommitted(false)
    setImageAnalysis(null)
    setPendingFile(null)
    setAnalysisError(null)
  }

  function handleImageError() {
    setAnalysisError("Bilden kunde inte laddas. Kontrollera URL:en.")
    setImageCommitted(false)
  }

  const canAnalyze = pendingFile !== null || imageUrl.trim().length > 0

  // ── LÄGE 1 — ingen bild ──────────────────────────────────────────────────
  if (!imageCommitted) {
    return (
      <div
        className="bg-surface-container-low rounded-xl p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-headline text-sm font-bold text-primary mb-3">Product Image</h2>
        <div
          className="border-2 border-dashed border-outline-variant rounded-lg p-6 text-center mb-3"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="material-symbols-outlined text-on-surface-variant block mb-2 opacity-30 text-4xl">
            image
          </span>
          <p className="text-sm text-on-surface-variant">Lägg till bild-URL</p>
          <label
            className="cursor-pointer text-xs text-primary font-medium hover:underline flex items-center justify-center gap-1 mt-2"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="material-symbols-outlined text-[14px]">upload</span>
            Ladda upp
            <input type="file" accept="image/*" hidden onChange={handleFileUpload} />
          </label>
        </div>
        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
          <input
            type="text"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAnalyze()
            }}
            placeholder="https://..."
            className="flex-1 text-sm px-3 py-2 bg-surface-container rounded-xl border border-outline-variant focus:outline-none focus:border-primary text-on-surface placeholder:text-on-surface-variant transition-colors"
          />
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleAnalyze() }}
            disabled={!imageUrl.trim() || analyzingImage}
            className="px-3 py-2 text-xs font-medium rounded-xl bg-primary text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-container transition-colors shrink-0"
          >
            Analysera
          </button>
        </div>
        {analysisError && (
          <p className="text-xs text-error mt-2">{analysisError}</p>
        )}
      </div>
    )
  }

  // ── LÄGE 2 — bild visad, ej analyserad ───────────────────────────────────
  if (!imageAnalysis) {
    return (
      <div
        className="bg-surface-container-low rounded-xl p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-headline text-sm font-bold text-primary mb-3">Product Image</h2>
        <div className="relative rounded-lg overflow-hidden mb-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt="Product"
            onError={handleImageError}
            className={`w-full rounded-lg object-cover aspect-square transition-opacity ${analyzingImage ? "opacity-60" : ""}`}
          />
          {analyzingImage && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 rounded-lg gap-3">
              <div className="w-8 h-8 border-[3px] border-white/30 border-t-white rounded-full animate-spin" />
              <p className="text-white text-sm font-medium">Analyserar bild...</p>
              <div className="w-3/4 h-1.5 bg-white/20 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full animate-pulse w-2/3" />
              </div>
            </div>
          )}
        </div>
        {!analyzingImage && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleAnalyze() }}
            disabled={!canAnalyze}
            className="w-full flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-xl bg-primary text-white disabled:opacity-40 hover:bg-primary-container transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
            Analysera bild med AI
          </button>
        )}
        <div className="flex items-center justify-between mt-2">
          {analysisError && <p className="text-xs text-error">{analysisError}</p>}
          <label
            className="cursor-pointer text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 ml-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="material-symbols-outlined text-[13px]">upload</span>
            Byt bild
            <input type="file" accept="image/*" hidden onChange={handleFileUpload} />
          </label>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); resetToLage1() }}
            className="text-xs text-on-surface-variant hover:text-on-surface transition-colors ml-3"
          >
            Ändra URL
          </button>
        </div>
      </div>
    )
  }

  // ── LÄGE 3 — bild analyserad ─────────────────────────────────────────────
  const attrEntries = Object.entries(imageAnalysis.detected_attributes)
  const tagValues = Object.values(imageAnalysis.detected_attributes)

  return (
    <div
      className="bg-surface-container-low rounded-xl p-4"
      onClick={(e) => e.stopPropagation()}
    >
      <h2 className="font-headline text-sm font-bold text-primary mb-3">Product Image</h2>

      {/* Bild med score-badge */}
      <div className="relative rounded-lg overflow-hidden mb-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt="Product"
          onError={handleImageError}
          className="w-full rounded-lg object-cover aspect-square"
        />
        <span
          className={`absolute top-0 left-0 text-white text-xs font-bold px-2 py-1 rounded-br-lg ${qualityBadgeClass(imageAnalysis.image_quality_score)}`}
        >
          VISUAL QUALITY: {imageAnalysis.image_quality_score}%
        </span>
      </div>

      {/* Detekterade attribut */}
      {attrEntries.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant mb-1.5">
            Detekterade attribut
          </p>
          <dl className="space-y-1">
            {attrEntries.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="text-xs text-on-surface-variant capitalize">{k}</dt>
                <dd className="text-xs font-medium text-on-surface text-right">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Visuella taggar */}
      {tagValues.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant mb-1.5">
            Visuella taggar
          </p>
          <div className="flex flex-wrap gap-1">
            {tagValues.map((tag, i) => (
              <span
                key={i}
                className="bg-primary/10 text-primary text-xs rounded-full px-2 py-0.5"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Bildproblem */}
      {imageAnalysis.quality_issues.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant mb-1.5 flex items-center gap-1">
            <span className="material-symbols-outlined text-[13px] text-[#856404]">warning</span>
            Bildproblem
          </p>
          <ul className="space-y-1">
            {imageAnalysis.quality_issues.map((issue, i) => (
              <li key={i} className="text-xs text-error flex items-start gap-1">
                <span className="material-symbols-outlined text-[12px] mt-0.5 shrink-0">
                  error
                </span>
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setImageAnalysis(null) }}
        className="text-xs text-on-surface-variant hover:text-on-surface transition-colors mt-1"
      >
        Re-analysera
      </button>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProductDetailPage() {
  const router = useRouter()
  const params = useParams()
  const skuId = params.sku_id as string

  const [product, setProduct] = useState<ProductDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [enriching, setEnriching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, boolean | null>>({})
  const [editedValues, setEditedValues] = useState<Record<string, string>>({})
  const [editingField, setEditingField] = useState<string | null>(null)

  const fetchProduct = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get<ProductDetailResponse>(`/api/v1/products/${skuId}`)
      setProduct(data)
      const initial: Record<string, boolean | null> = {}
      data.enriched_fields.forEach((f) => {
        initial[f.field] = null
      })
      setDecisions(initial)
      setEditedValues({})
      setEditingField(null)
    } catch {
      setError("Kunde inte ladda produkten.")
    } finally {
      setLoading(false)
    }
  }, [skuId])

  useEffect(() => {
    fetchProduct()
  }, [fetchProduct])

  async function handleEnrich() {
    setEnriching(true)
    try {
      await api.post<EnrichResponse>(`/api/v1/products/${skuId}/enrich`)
      await fetchProduct()
    } catch {
      setError("Enrichment misslyckades. Försök igen.")
      setEnriching(false)
    }
  }

  function decide(field: string, accepted: boolean) {
    setDecisions((prev) => ({ ...prev, [field]: accepted }))
  }

  function startEdit(field: string, originalValue: string) {
    setEditedValues((prev) => ({ ...prev, [field]: prev[field] ?? originalValue }))
    setEditingField(field)
  }

  function stopEdit() {
    setEditingField(null)
  }

  function cancelEdit(field: string) {
    setEditedValues((prev) => {
      const next = { ...prev }
      delete next[field]
      return next
    })
    setEditingField(null)
  }

  function updateEditedValue(field: string, value: string) {
    setEditedValues((prev) => ({ ...prev, [field]: value }))
  }

  function acceptAll() {
    if (!product) return
    const next: Record<string, boolean | null> = {}
    product.enriched_fields.forEach((f) => {
      next[f.field] = true
    })
    setDecisions(next)
  }

  function exportAccepted() {
    if (!product) return
    const accepted: Record<string, string> = {}
    product.enriched_fields.forEach((f) => {
      if (decisions[f.field] === true)
        accepted[f.field] = editedValues[f.field] ?? f.suggested_value
    })
    const blob = new Blob(
      [JSON.stringify({ sku_id: product.sku_id, ...accepted }, null, 2)],
      { type: "application/json" }
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${product.sku_id}_enriched.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  function sendToPIM() {
    if (!product) return
    const acceptedFields: Record<string, string> = {}
    product.enriched_fields.forEach((f) => {
      if (decisions[f.field] === true)
        acceptedFields[f.field] = editedValues[f.field] ?? f.suggested_value
    })
    console.log("Send to PIM:", { sku_id: product.sku_id, fields: acceptedFields })
  }

  const acceptedCount = Object.values(decisions).filter((v) => v === true).length
  const hasEnrichments = product && product.enriched_fields.length > 0
  const risk = riskConfig(product?.return_risk ?? null)

  return (
    <div className="min-h-full bg-background">
      {/* Header */}
      <div className="bg-surface-container-lowest border-b border-outline-variant px-8 py-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-1 text-sm text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
            >
              <span className="material-symbols-outlined text-[18px]">arrow_back</span>
              Back
            </button>
            <span className="text-outline-variant shrink-0">·</span>
            <span className="font-mono text-sm text-on-surface-variant shrink-0">{skuId}</span>
            {product && (
              <>
                <span className="text-outline-variant shrink-0">·</span>
                <h1 className="font-headline text-lg font-bold text-on-surface truncate">
                  {product.title ?? "—"}
                </h1>
              </>
            )}
          </div>

          <div className="flex items-center gap-3 shrink-0 ml-4">
            {product && product.overall_score !== null && (
              <div
                className={`w-10 h-10 rounded-full border-2 flex items-center justify-center text-xs font-bold shrink-0 ${scoreClass(product.overall_score)}`}
              >
                {product.overall_score}
              </div>
            )}
            <button
              onClick={handleEnrich}
              disabled={enriching}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl bg-primary text-white hover:bg-primary-container transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {enriching ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
              )}
              {enriching ? "Enriching…" : product?.enriched_at ? "Re-enrich" : "Enrich"}
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-8 py-6">
        {loading ? (
          <DetailSkeleton />
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-24">
            <span className="material-symbols-outlined text-[48px] text-error mb-3">error</span>
            <p className="text-on-surface-variant font-medium">{error}</p>
            <button
              onClick={fetchProduct}
              className="mt-4 px-4 py-2 text-sm font-medium rounded-xl bg-primary text-white hover:bg-primary-container transition-colors"
            >
              Retry
            </button>
          </div>
        ) : product ? (
          <div className="grid grid-cols-12 gap-6">
            {/* ── Left column ──────────────────────────────────────────── */}
            <div className="col-span-8 space-y-4">
              {/* Enriched fields */}
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant">
                  <div>
                    <h2 className="font-headline text-base font-bold text-on-surface">
                      Enriched Fields
                    </h2>
                    {hasEnrichments && (
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        {acceptedCount} of {product.enriched_fields.length} accepted
                      </p>
                    )}
                  </div>
                  {hasEnrichments && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={acceptAll}
                        className="px-3 py-1.5 text-xs font-medium rounded-xl bg-surface-container text-on-surface hover:bg-surface-container-high transition-colors"
                      >
                        Accept all
                      </button>
                      <button
                        onClick={exportAccepted}
                        disabled={acceptedCount === 0}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-xl border border-outline-variant text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container transition-colors"
                      >
                        <span className="material-symbols-outlined text-[14px]">download</span>
                        Export JSON
                      </button>
                      <button
                        onClick={sendToPIM}
                        disabled={acceptedCount === 0}
                        className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-xl bg-primary text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-container transition-colors"
                      >
                        <span className="material-symbols-outlined text-[16px]">upload_file</span>
                        Send to PIM
                      </button>
                    </div>
                  )}
                </div>

                {!hasEnrichments ? (
                  <div className="flex flex-col items-center justify-center py-16">
                    <span className="material-symbols-outlined text-[48px] text-on-surface-variant mb-3">
                      auto_awesome
                    </span>
                    <p className="text-on-surface-variant font-medium">No enrichment data yet</p>
                    <p className="text-xs text-on-surface-variant mt-1 opacity-60">
                      Click Enrich to run AI analysis
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-outline-variant bg-surface-container-low">
                          <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                            Fält
                          </th>
                          <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                            Nuvarande värde
                          </th>
                          <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                            AI-förslag
                          </th>
                          <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                            Confidence
                          </th>
                          <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                            Åtgärd
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {product.enriched_fields.map((field) => (
                          <EnrichmentTableRow
                            key={field.field}
                            field={field}
                            currentValue={getCurrentValue(field.field, product)}
                            decision={decisions[field.field] ?? null}
                            onDecide={decide}
                            editedValues={editedValues}
                            editingField={editingField}
                            onStartEdit={startEdit}
                            onStopEdit={stopEdit}
                            onCancelEdit={cancelEdit}
                            onUpdateEditedValue={updateEditedValue}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Quality issues */}
              {product.issues.length > 0 && (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                  <div className="px-5 py-4 border-b border-outline-variant">
                    <h2 className="font-headline text-base font-bold text-on-surface">
                      Quality Issues
                    </h2>
                  </div>
                  <div className="divide-y divide-outline-variant">
                    {product.issues.map((issue, i) => (
                      <div key={i} className="px-5 py-3 flex items-start gap-3">
                        <span
                          className={`material-symbols-outlined text-[18px] mt-0.5 shrink-0 ${
                            issue.severity === "high"
                              ? "text-error"
                              : issue.severity === "medium"
                              ? "text-[#856404]"
                              : "text-on-surface-variant"
                          }`}
                        >
                          {issue.severity === "high"
                            ? "error"
                            : issue.severity === "medium"
                            ? "warning"
                            : "info"}
                        </span>
                        <div>
                          <p className="text-sm font-medium text-on-surface">
                            <span className="font-mono text-xs bg-surface-container px-1.5 py-0.5 rounded mr-2">
                              {issue.field}
                            </span>
                            {issue.problem}
                          </p>
                          <p className="text-xs text-on-surface-variant mt-0.5">
                            {issue.suggestion}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action items */}
              {product.action_items.length > 0 && (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                  <div className="px-5 py-4 border-b border-outline-variant">
                    <h2 className="font-headline text-base font-bold text-on-surface">
                      Action Items
                    </h2>
                  </div>
                  <ul className="divide-y divide-outline-variant">
                    {product.action_items.map((item, i) => (
                      <li
                        key={i}
                        className="px-5 py-3 flex items-center gap-3 text-sm text-on-surface"
                      >
                        <span className="material-symbols-outlined text-[16px] text-primary shrink-0">
                          task_alt
                        </span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Overall score summary */}
              {product.overall_score !== null && (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                  <div className="px-5 py-4 border-b border-outline-variant">
                    <h2 className="font-headline text-base font-bold text-on-surface">
                      Overall Content Score
                    </h2>
                  </div>
                  <div className="px-5 py-5 flex items-center gap-5">
                    {(() => {
                      const s = product.overall_score!
                      const { text, color } = scoreLabel(s)
                      const border = scoreBorderColor(s)
                      return (
                        <>
                          <div
                            className={`w-16 h-16 rounded-full border-4 flex items-center justify-center font-bold text-xl shrink-0 ${border} ${color}`}
                          >
                            {s}
                          </div>
                          <div>
                            <p className={`text-lg font-bold ${color}`}>{text}</p>
                            <p className="text-xs text-on-surface-variant mt-0.5">
                              Score {s} / 100
                            </p>
                          </div>
                        </>
                      )
                    })()}
                  </div>
                </div>
              )}
            </div>

            {/* ── Right column ─────────────────────────────────────────── */}
            <div className="col-span-4 space-y-4">
              {/* Image panel */}
              <ImagePanel skuId={skuId} initialImageUrl={product.image_url} />

              {/* Return risk */}
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                <div className="px-5 py-4 border-b border-outline-variant">
                  <h2 className="font-headline text-base font-bold text-on-surface">
                    Return Risk
                  </h2>
                </div>
                <div className="px-5 py-4">
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold ${risk.className}`}
                  >
                    <span className="material-symbols-outlined text-[16px]">{risk.icon}</span>
                    {risk.label}
                  </span>
                  {product.return_risk_reason && (
                    <p className="text-sm text-on-surface-variant mt-3 leading-relaxed">
                      {product.return_risk_reason}
                    </p>
                  )}
                </div>
              </div>

              {/* Product info */}
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                <div className="px-5 py-4 border-b border-outline-variant">
                  <h2 className="font-headline text-base font-bold text-on-surface">
                    Product Info
                  </h2>
                </div>
                <dl className="divide-y divide-outline-variant">
                  {[
                    { label: "Title", value: product.title },
                    { label: "Category", value: product.category },
                    { label: "Brand", value: product.brand },
                    {
                      label: "Price",
                      value: product.price != null ? `${product.price} kr` : null,
                    },
                  ]
                    .filter((r) => r.value)
                    .map(({ label, value }) => (
                      <div key={label} className="px-5 py-2.5 flex justify-between gap-4">
                        <dt className="text-xs text-on-surface-variant shrink-0">{label}</dt>
                        <dd className="text-xs text-on-surface text-right font-medium">{value}</dd>
                      </div>
                    ))}
                </dl>
              </div>

              {/* Feed info */}
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                <div className="px-5 py-4 border-b border-outline-variant">
                  <h2 className="font-headline text-base font-bold text-on-surface">Feed Info</h2>
                </div>
                <dl className="divide-y divide-outline-variant">
                  {[
                    { label: "Feed source", value: product.feed_source },
                    { label: "Detected source", value: product.detected_source },
                    {
                      label: "Enriched at",
                      value: product.enriched_at
                        ? new Date(product.enriched_at).toLocaleString("sv-SE")
                        : null,
                    },
                    { label: "Prompt version", value: product.prompt_version },
                    {
                      label: "Total tokens",
                      value: product.total_tokens?.toLocaleString() ?? null,
                    },
                  ]
                    .filter((r) => r.value)
                    .map(({ label, value }) => (
                      <div key={label} className="px-5 py-2.5 flex justify-between gap-4">
                        <dt className="text-xs text-on-surface-variant shrink-0">{label}</dt>
                        <dd className="text-xs text-on-surface text-right font-medium font-mono">
                          {value}
                        </dd>
                      </div>
                    ))}
                </dl>
              </div>

              {/* Raw attributes */}
              {Object.keys(product.attributes).length > 0 && (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
                  <div className="px-5 py-4 border-b border-outline-variant">
                    <h2 className="font-headline text-base font-bold text-on-surface">
                      Attributes
                    </h2>
                  </div>
                  <dl className="divide-y divide-outline-variant">
                    {Object.entries(product.attributes).map(([k, v]) => (
                      <div key={k} className="px-5 py-2.5 flex justify-between gap-4">
                        <dt className="text-xs text-on-surface-variant shrink-0 capitalize">
                          {k}
                        </dt>
                        <dd className="text-xs text-on-surface text-right font-medium">
                          {String(v)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
