"use client"

import { useState, useEffect, useCallback } from "react"
import { api } from "@/lib/api"
import type { StatsResponse, JobResponse, BulkEnrichResponse, JobListItem } from "@/lib/types"

// ── Types ──────────────────────────────────────────────────────────────────────

type BatchStatus = "success" | "warning" | "failed"
type BatchSize = 10 | 25 | 50 | "all"
type ProductSelection = "all_unenriched" | "failed_only" | "custom"

interface HistoryBatch {
  id: string
  date: string
  jobName: string
  skus: number
  ok: number
  failed: number
  successRate: number
  status: BatchStatus
  startedAt: string
  finishedAt: string
  duration: string
}

// ── Map API JobListItem → HistoryBatch ─────────────────────────────────────────

function toHistoryBatch(job: JobListItem): HistoryBatch {
  const date = new Date(job.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })

  const startedAt = job.started_at
    ? new Date(job.started_at).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—"

  const finishedAt = job.completed_at
    ? new Date(job.completed_at).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—"

  let duration = "—"
  if (job.started_at && job.completed_at) {
    const secs = Math.floor(
      (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000
    )
    const mins = Math.floor(secs / 60)
    const s = secs % 60
    duration = mins > 0 ? `${mins} min ${s} sec` : `${s} sec`
  }

  const successRate =
    job.total > 0 ? Math.round((job.processed / job.total) * 1000) / 10 : 0

  let status: BatchStatus
  if (job.status === "failed" || (job.status === "completed" && job.processed === 0 && job.total > 0)) {
    status = "failed"
  } else if (job.status === "completed" && job.failed > 0) {
    status = "warning"
  } else {
    status = "success"
  }

  return {
    id: job.id.slice(0, 8),
    date,
    jobName: job.job_type,
    skus: job.total,
    ok: job.processed,
    failed: job.failed,
    successRate,
    status,
    startedAt,
    finishedAt,
    duration,
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatElapsed(startedAt: string | null): string {
  if (!startedAt) return "0m 0s"
  const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  return `${mins}m ${secs}s`
}

function estimateTime(size: BatchSize): string {
  if (size === 10) return "~4 min"
  if (size === 25) return "~11 min"
  if (size === 50) return "~22 min"
  return "~10 min"
}

function statusStyle(status: BatchStatus) {
  if (status === "success") return { pill: "bg-[#dcfce7] text-[#16a34a]", bar: "#16a34a", label: "SUCCESS" }
  if (status === "warning") return { pill: "bg-[#fef3c7] text-[#d97706]", bar: "#d97706", label: "WARNING" }
  return { pill: "bg-[#fee2e2] text-[#dc2626]", bar: "#dc2626", label: "FAILED" }
}

// ── ProgressBar ────────────────────────────────────────────────────────────────

function ProgressBar({
  pct,
  color = "#1e3a5f",
  animated = false,
  height = "h-2.5",
}: {
  pct: number
  color?: string
  animated?: boolean
  height?: string
}) {
  return (
    <div className={`relative ${height} bg-[#e5e7eb] rounded-full overflow-hidden`}>
      <div
        className="absolute inset-y-0 left-0 rounded-full"
        style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }}
      >
        {animated && (
          <div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/25 to-transparent"
            style={{ animation: "shimmer 2s ease-in-out infinite" }}
          />
        )}
      </div>
    </div>
  )
}

// ── NewBatchModal ──────────────────────────────────────────────────────────────

function NewBatchModal({
  onClose,
  onStart,
  stats,
}: {
  onClose: () => void
  onStart: (size: BatchSize, selection: ProductSelection, name: string) => void
  stats: StatsResponse | null
}) {
  const [batchName, setBatchName] = useState("")
  const [selection, setSelection] = useState<ProductSelection>("all_unenriched")
  const [batchSize, setBatchSize] = useState<BatchSize>(25)

  const unenrichedCount = stats ? stats.total_products - stats.enriched : 0
  const failedCount = stats?.failed ?? 0

  const productOptions: Array<{
    id: ProductSelection
    label: string
    badge: string | null
    badgeClass: string
    chevron?: boolean
  }> = [
    {
      id: "all_unenriched",
      label: "All unenriched",
      badge: `${unenrichedCount} products`,
      badgeClass: "bg-[#f3f4f6] text-[#374151]",
    },
    {
      id: "failed_only",
      label: "Failed only",
      badge: `${failedCount} products`,
      badgeClass: "bg-[#fee2e2] text-[#dc2626]",
    },
    {
      id: "custom",
      label: "Custom selection...",
      badge: null,
      badgeClass: "",
      chevron: true,
    },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-[560px] max-h-[90vh] overflow-y-auto">
        <div className="p-8">
          <h2 className="text-[22px] font-bold text-[#111827] mb-1">Start new batch</h2>
          <p className="text-sm text-[#6b7280] mb-7">Configure your enrichment pipeline parameters.</p>

          {/* Batch Name */}
          <div className="mb-6">
            <label className="block text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-2">
              Batch Name
            </label>
            <input
              type="text"
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="e.g. Spring collection 2026"
              className="w-full px-4 py-3 rounded-xl bg-[#fafaf7] border border-[#e5e7eb] text-[#111827] placeholder-[#9ca3af] text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] transition-colors"
            />
          </div>

          {/* Products to Enrich */}
          <div className="mb-6">
            <label className="block text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-2">
              Products to Enrich
            </label>
            <div className="space-y-2">
              {productOptions.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSelection(opt.id)}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-all ${
                    selection === opt.id
                      ? "bg-[#eff6ff] border-[#1e3a5f]"
                      : "bg-white border-[#e5e7eb] hover:bg-[#f9fafb]"
                  }`}
                  style={{
                    border: `1px solid`,
                    borderColor: selection === opt.id ? "#1e3a5f" : "#e5e7eb",
                    borderLeft: selection === opt.id ? "4px solid #1e3a5f" : "1px solid #e5e7eb",
                  }}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                        selection === opt.id ? "border-[#1e3a5f]" : "border-[#d1d5db]"
                      }`}
                    >
                      {selection === opt.id && (
                        <div className="w-2 h-2 rounded-full bg-[#1e3a5f]" />
                      )}
                    </div>
                    <span className="text-sm font-medium text-[#111827]">{opt.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {opt.badge && (
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${opt.badgeClass}`}>
                        {opt.badge}
                      </span>
                    )}
                    {opt.chevron && <span className="text-[#9ca3af]">›</span>}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Batch Size */}
          <div className="mb-8">
            <label className="block text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-2">
              Batch Size
            </label>
            <div className="grid grid-cols-4 gap-2 border border-[#e5e7eb] rounded-xl p-1 bg-[#f9fafb]">
              {([10, 25, 50, "all"] as BatchSize[]).map((size) => (
                <button
                  key={size}
                  onClick={() => setBatchSize(size)}
                  className={`py-2 rounded-lg text-sm font-semibold transition-all ${
                    batchSize === size
                      ? "bg-[#1e3a5f] text-white shadow-sm"
                      : "text-[#374151] hover:bg-white"
                  }`}
                >
                  {size === "all" ? "All" : size}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-[#9ca3af] italic">
              Estimate processing time: {estimateTime(batchSize)}
            </p>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between">
            <button
              onClick={onClose}
              className="text-sm text-[#6b7280] hover:text-[#111827] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onStart(batchSize, selection, batchName)}
              className="flex items-center gap-2 px-6 py-2.5 bg-[#1e3a5f] text-white text-sm font-bold rounded-full hover:bg-[#2d4f7c] transition-colors shadow-md shadow-[#1e3a5f]/20"
            >
              <span>✦</span>
              Start enrichment
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── JobDetailPanel ─────────────────────────────────────────────────────────────

function JobDetailPanel({
  batch,
  onClose,
}: {
  batch: HistoryBatch
  onClose: () => void
}) {
  const style = statusStyle(batch.status)

  const statusLabel =
    batch.status === "success"
      ? "● Completed"
      : batch.status === "warning"
      ? "● Completed (partial)"
      : "● Failed"

  const statusColor =
    batch.status === "success"
      ? "text-[#16a34a]"
      : batch.status === "warning"
      ? "text-[#d97706]"
      : "text-[#dc2626]"

  return (
    <div className="fixed right-0 top-0 h-screen w-[400px] z-40 bg-white border-l border-[#e5e7eb] shadow-2xl shadow-black/10 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e7eb]">
        <h3 className="font-bold text-[#111827] text-base">Job Details</h3>
        <button
          onClick={onClose}
          className="text-[#9ca3af] hover:text-[#111827] w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[#f3f4f6] transition-colors text-lg"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
        {/* Metadata */}
        <div className="space-y-2.5 text-sm">
          {[
            { label: "ID", value: batch.id, mono: true, colorClass: "" },
            { label: "Type", value: batch.jobName, mono: true, colorClass: "" },
            { label: "Status", value: statusLabel, mono: false, colorClass: statusColor },
            { label: "Started", value: batch.startedAt, mono: false, colorClass: "" },
            { label: "Finished", value: batch.finishedAt, mono: false, colorClass: "" },
            { label: "Duration", value: batch.duration, mono: false, colorClass: "" },
          ].map(({ label, value, mono, colorClass }) => (
            <div key={label} className="flex justify-between items-center">
              <span className="text-[#6b7280]">{label}</span>
              <span
                className={`font-medium ${
                  mono ? "font-mono text-xs text-[#374151]" : colorClass || "text-[#111827]"
                }`}
              >
                {value}
              </span>
            </div>
          ))}
        </div>

        {/* Result Summary */}
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-3">
            Result Summary
          </p>
          <div className="bg-[#f9fafb] rounded-xl p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-[#6b7280]">Total SKUs</span>
              <span className="font-bold text-[#111827]">{batch.skus}</span>
            </div>
            <ProgressBar pct={batch.successRate} color={style.bar} />
            <div className="flex justify-between text-xs">
              <span className="text-[#16a34a] font-medium">✅ Succeeded: {batch.ok}</span>
              <span className="text-[#dc2626] font-medium">❌ Failed: {batch.failed}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="px-6 py-4 border-t border-[#e5e7eb] space-y-2">
        <button className="w-full py-2.5 rounded-full border-2 border-[#1e3a5f] text-[#1e3a5f] text-sm font-semibold hover:bg-[#1e3a5f] hover:text-white transition-all">
          🔄 Retry failed products
        </button>
        <button className="w-full py-2.5 rounded-full border border-[#e5e7eb] text-[#374151] text-sm font-medium hover:bg-[#f9fafb] transition-all">
          📥 Export as CSV
        </button>
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ProcessingPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [activeJob, setActiveJob] = useState<JobResponse | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [selectedBatch, setSelectedBatch] = useState<HistoryBatch | null>(null)
  const [, setElapsedTick] = useState(0)
  const [history, setHistory] = useState<HistoryBatch[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [startError, setStartError] = useState<string | null>(null)

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await api.get<StatsResponse>("/api/v1/stats")
      setStats(data)
    } catch {
      // silent
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const { data } = await api.get<JobListItem[]>("/api/v1/jobs", {
        params: { limit: 20 },
      })
      setHistory(data.map(toHistoryBatch))
      setHistoryTotal(data.length)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    fetchStats()
    fetchHistory()
  }, [fetchStats, fetchHistory])

  // Restore active job from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("fp_active_job_id")
    const savedAt = localStorage.getItem("fp_active_job_started_at")
    if (saved) {
      setJobId(saved)
      setStartedAt(savedAt)
    }
  }, [])

  // Poll active job
  useEffect(() => {
    if (!jobId) return

    const interval = setInterval(async () => {
      try {
        const { data } = await api.get<JobResponse>(`/api/v1/jobs/${jobId}`)
        setActiveJob(data)

        const done =
          data.status === "complete" ||
          data.status === "completed" ||
          data.status === "failed"

        if (done) {
          clearInterval(interval)
          setJobId(null)
          setActiveJob(null)
          localStorage.removeItem("fp_active_job_id")
          localStorage.removeItem("fp_active_job_started_at")
          fetchStats()
          fetchHistory()
        }
      } catch {
        clearInterval(interval)
        setJobId(null)
        setActiveJob(null)
        localStorage.removeItem("fp_active_job_id")
        localStorage.removeItem("fp_active_job_started_at")
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [jobId, fetchStats, fetchHistory])

  // Elapsed ticker — forces re-render every second when a job is running
  useEffect(() => {
    if (!activeJob) return
    const t = setInterval(() => setElapsedTick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [activeJob])

  async function handleStartBatch(size: BatchSize, _selection: ProductSelection, _name: string) {
    setShowModal(false)
    setStartError(null)
    const limit = size === "all" ? 9999 : size
    try {
      const { data } = await api.post<BulkEnrichResponse>("/api/v1/enrich/bulk", { limit })
      const now = new Date().toISOString()
      setJobId(data.job_id)
      setStartedAt(now)
      setActiveJob({
        job_id: data.job_id,
        status: "queued",
        progress_pct: 0,
        processed: 0,
        total: 0,
        failed: 0,
      })
      localStorage.setItem("fp_active_job_id", data.job_id)
      localStorage.setItem("fp_active_job_started_at", now)
    } catch (err) {
      console.error("[ProcessingPage] POST /enrich/bulk failed:", err)
      setStartError("Kunde inte starta batch. Kontrollera att backend körs och försök igen.")
    }
  }

  const isRunning =
    !!activeJob &&
    activeJob.status !== "complete" &&
    activeJob.status !== "completed" &&
    activeJob.status !== "failed"

  const pct = activeJob?.progress_pct ?? 0
  const processed = activeJob?.processed ?? 0
  const total = activeJob?.total ?? 0

  const totalEnriched = stats?.enriched ?? 0
  const totalProducts = stats?.total_products ?? 0
  const enrichPct =
    totalProducts > 0 ? ((totalEnriched / totalProducts) * 100).toFixed(1) : "0"

  return (
    <div className="min-h-full bg-[#f8f9fc]">
      {/* Page header */}
      <header className="bg-white border-b border-[#e5e7eb] px-8 py-6">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-[28px] font-bold text-[#111827] leading-tight">Batch Processing</h1>
            <p className="text-sm text-[#6b7280] mt-1">Monitor and manage AI enrichment jobs</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#1e3a5f] text-white text-sm font-bold rounded-full hover:bg-[#2d4f7c] transition-colors shadow-md shadow-[#1e3a5f]/20"
          >
            <span>✦</span>
            New Batch
          </button>
        </div>
      </header>

      <div className="px-8 py-8 space-y-10">
        {/* ── Error banner ──────────────────────────────────────────────────── */}
        {startError && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 px-4 py-3 bg-[#fee2e2] border border-[#fca5a5] rounded-[10px] text-sm text-[#dc2626]"
          >
            <span>{startError}</span>
            <button
              onClick={() => setStartError(null)}
              className="shrink-0 text-[#dc2626]/60 hover:text-[#dc2626] transition-colors"
            >
              ✕
            </button>
          </div>
        )}

        {/* ── Stats row ──────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-5">
          {/* Active Jobs */}
          <div className="bg-white rounded-[12px] border border-[#e5e7eb] p-6">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-3">Active Jobs</p>
            <p className="text-4xl font-bold text-[#111827] mb-2">{isRunning ? 1 : 0}</p>
            <div className="flex items-center gap-1.5 text-sm">
              <span
                className={`w-2 h-2 rounded-full ${
                  isRunning
                    ? activeJob?.status === "queued"
                      ? "bg-[#d97706]"
                      : "bg-[#16a34a]"
                    : "bg-[#d1d5db]"
                }`}
              />
              <span
                className={
                  isRunning
                    ? activeJob?.status === "queued"
                      ? "text-[#d97706] font-semibold"
                      : "text-[#16a34a] font-semibold"
                    : "text-[#6b7280]"
                }
              >
                {isRunning
                  ? activeJob?.status === "queued"
                    ? "QUEUED"
                    : "RUNNING"
                  : "Idle"}
              </span>
            </div>
          </div>

          {/* Total Enriched */}
          <div className="bg-white rounded-[12px] border border-[#e5e7eb] p-6">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-3">Total Enriched</p>
            <p className="text-4xl font-bold text-[#111827] mb-2">{totalEnriched}</p>
            <p className="text-sm text-[#6b7280]">
              of <span className="font-medium text-[#374151]">{totalProducts} products</span>{" "}
              ({enrichPct}%)
            </p>
          </div>

          {/* Avg Success Rate */}
          <div className="bg-white rounded-[12px] border border-[#e5e7eb] p-6">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6b7280] mb-3">Avg Success Rate</p>
            <p className="text-4xl font-bold text-[#d97706] mb-2">8.7%</p>
            <p className="text-sm text-[#6b7280]">last 10 jobs</p>
          </div>
        </div>

        {/* ── Active Jobs ────────────────────────────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-[20px] text-[#374151]">settings</span>
            <h2 className="text-lg font-bold text-[#111827]">Active Jobs</h2>
          </div>

          {isRunning && activeJob ? (
            <div
              className="bg-white rounded-[12px] border border-[#e5e7eb] p-6 shadow-sm"
              style={{ borderLeft: "4px solid #16a34a" }}
            >
              {/* Top row */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-[18px] text-[#6b7280]">settings</span>
                  <span className="font-semibold text-[#111827]">enrich_bulk</span>
                  {activeJob.status === "queued" ? (
                    <span className="px-2.5 py-0.5 bg-[#fef3c7] text-[#d97706] text-[11px] font-bold rounded-full">
                      ● QUEUED
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 bg-[#dcfce7] text-[#16a34a] text-[11px] font-bold rounded-full">
                      ● RUNNING
                    </span>
                  )}
                </div>
                <div className="text-xs text-[#6b7280] text-right space-y-0.5">
                  <div>
                    Started:{" "}
                    {startedAt
                      ? new Date(startedAt).toLocaleTimeString("en-GB", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </div>
                  <div>Elapsed: {formatElapsed(startedAt)}</div>
                </div>
              </div>

              {/* Progress label */}
              <div className="flex items-center justify-between mb-2">
                {activeJob.status === "queued" ? (
                  <>
                    <span className="font-bold text-[#111827]">Queuing...</span>
                    <span className="text-sm text-[#6b7280]">Waiting for worker</span>
                  </>
                ) : (
                  <>
                    <span className="font-bold text-[#111827]">{pct}% Complete</span>
                    <span className="text-sm text-[#6b7280]">{processed} / {total} Products</span>
                  </>
                )}
              </div>

              {/* Progress bar — indeterminate shimmer when queued, actual progress when running */}
              <ProgressBar
                pct={activeJob.status === "queued" ? 5 : pct}
                animated
                height="h-3"
              />

              {/* Stats below bar — only meaningful once running */}
              {activeJob.status !== "queued" && (
                <div className="flex items-center gap-6 mt-3 text-sm">
                  <span className="text-[#16a34a] font-medium">✅ Succeeded: {processed}</span>
                  <span className="text-[#dc2626] font-medium">❌ Failed: {activeJob.failed ?? 0}</span>
                  <span className="text-[#6b7280]">⏳ Remaining: {total - processed - (activeJob.failed ?? 0)}</span>
                </div>
              )}

              {/* Bottom row */}
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-[#9ca3af] italic">
                  {activeJob.status === "queued"
                    ? "Starting enrichment pipeline..."
                    : activeJob.eta_seconds != null
                    ? `Est. completion: ~${Math.ceil(activeJob.eta_seconds / 60)} min`
                    : "Estimating completion time..."}
                </span>
                <button className="text-xs text-[#9ca3af] hover:text-[#dc2626] transition-colors">
                  Cancel
                </button>
              </div>

              {/* Job ID */}
              <p className="mt-3 text-[10px] font-mono text-[#c4c9d4]">#{jobId?.slice(0, 8)}</p>
            </div>
          ) : (
            <div className="border-2 border-dashed border-[#e5e7eb] rounded-[12px] py-12 flex flex-col items-center gap-3 text-center bg-white">
              <span className="text-4xl">📭</span>
              <p className="font-semibold text-[#374151] text-base">No active jobs</p>
              <p className="text-sm text-[#6b7280]">Start a batch to enrich your catalog with AI</p>
              <button
                onClick={() => setShowModal(true)}
                className="mt-2 flex items-center gap-2 px-5 py-2 bg-[#1e3a5f] text-white text-sm font-bold rounded-full hover:bg-[#2d4f7c] transition-colors"
              >
                <span>✦</span>
                Start enrichment
              </button>
            </div>
          )}
        </section>

        {/* ── Processing History ─────────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[20px] text-[#374151]">history</span>
              <h2 className="text-lg font-bold text-[#111827]">Processing History</h2>
            </div>
            {/* Filters */}
            <div className="flex items-center gap-2">
              {["All types", "All statuses", "Last 30 days"].map((label) => (
                <button
                  key={label}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#374151] border border-[#e5e7eb] rounded-lg bg-white hover:bg-[#f9fafb] transition-colors"
                >
                  {label}
                  <span className="text-[#9ca3af]">▾</span>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-[12px] border border-[#e5e7eb] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-[#e5e7eb] bg-[#f9fafb]">
                <tr>
                  {[
                    "Date",
                    "Job Name",
                    "SKUs",
                    "✅ OK",
                    "❌ Failed",
                    "Success Rate",
                    "Status",
                    "",
                  ].map((col) => (
                    <th
                      key={col}
                      className="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7280] uppercase tracking-wider"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((batch) => {
                  const style = statusStyle(batch.status)
                  return (
                    <tr
                      key={batch.id}
                      className="border-b border-[#f3f4f6] last:border-0 hover:bg-[#f9fafb] transition-colors group"
                    >
                      <td className="px-4 py-3.5 text-[#374151] font-medium">{batch.date}</td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2">
                          <span className="material-symbols-outlined text-[14px] text-[#9ca3af]">
                            settings
                          </span>
                          <span className="font-mono text-xs text-[#374151]">{batch.jobName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-[#374151]">{batch.skus}</td>
                      <td className="px-4 py-3.5 text-[#16a34a] font-semibold">{batch.ok}</td>
                      <td className="px-4 py-3.5 text-[#dc2626] font-semibold">{batch.failed}</td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-20">
                            <ProgressBar
                              pct={batch.successRate}
                              color={style.bar}
                              height="h-1.5"
                            />
                          </div>
                          <span
                            className="text-xs font-bold"
                            style={{ color: style.bar }}
                          >
                            {batch.successRate}%
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`px-2.5 py-0.5 text-[11px] font-bold rounded-full ${style.pill}`}
                        >
                          {style.label}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => setSelectedBatch(batch)}
                          className="text-xs text-[#9ca3af] hover:text-[#1e3a5f] font-medium transition-colors opacity-0 group-hover:opacity-100"
                        >
                          › Details
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Table footer */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-[#e5e7eb] bg-[#f9fafb]">
              <span className="text-xs text-[#6b7280]">Showing {history.length} of {historyTotal} historical batches</span>
              <div className="flex items-center gap-2">
                <button className="px-3 py-1.5 text-xs font-medium text-[#374151] border border-[#e5e7eb] rounded-lg bg-white hover:bg-[#f9fafb] transition-colors">
                  Previous
                </button>
                <button className="px-3 py-1.5 text-xs font-medium text-[#374151] border border-[#e5e7eb] rounded-lg bg-white hover:bg-[#f9fafb] transition-colors">
                  Next
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Footer */}
      <footer className="px-8 py-4 flex items-center justify-between border-t border-[#e5e7eb] bg-white">
        <div className="flex items-center gap-3 text-xs text-[#9ca3af]">
          <span>FeedPilot v0.1</span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] inline-block" />
            AI Nodes: Operational
          </span>
        </div>
        <p className="text-xs text-[#9ca3af]">© 2026 FeedPilot. High-Precision Product Enrichment.</p>
      </footer>

      {/* ── Overlays ──────────────────────────────────────────────────────────── */}
      {showModal && (
        <NewBatchModal
          onClose={() => setShowModal(false)}
          onStart={handleStartBatch}
          stats={stats}
        />
      )}

      {selectedBatch && (
        <JobDetailPanel
          batch={selectedBatch}
          onClose={() => setSelectedBatch(null)}
        />
      )}
    </div>
  )
}
