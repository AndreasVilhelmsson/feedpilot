"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import type { StatsResponse, JobResponse, BulkEnrichResponse, CatalogProduct, CatalogResponse } from "@/lib/types"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { UploadModal } from "@/components/ui/UploadModal"

// ── Helpers ── (chart data removed until backend aggregation endpoints exist)

// ── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(score: number) {
  if (score >= 75) return "text-[#1a7f4b]"
  if (score >= 50) return "text-tertiary-fixed-dim"
  return "text-error"
}

function statusBadge(status: string) {
  if (status === "success") return "bg-[#dcf5e8] text-[#1a7f4b]"
  if (status === "warning") return "bg-tertiary-fixed text-tertiary"
  return "bg-error-container text-on-error-container"
}

function statusLabel(status: string) {
  if (status === "success") return "Enriched"
  if (status === "warning") return "Needs review"
  return "Return risk"
}

type BulkStatus = "idle" | "processing" | "complete" | "failed"

function enrichButtonLabel(status: BulkStatus, progress: number): string {
  if (status === "processing") return `Processing... ${progress}%`
  if (status === "complete") return "✓ Done"
  if (status === "failed") return "Failed — retry?"
  return "Enrich all"
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string | null): string {
  if (!iso) return "—"
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return "nyss"
  if (mins < 60) return `${mins} min sedan`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} h sedan`
  return `${Math.floor(hours / 24)} d sedan`
}

function productStatusKey(status: string): "success" | "warning" | "error" {
  if (status === "enriched") return "success"
  if (status === "return_risk") return "error"
  return "warning"
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string
  value: string
  delta: string
  icon: string
  positive: boolean
  extraClass?: string
}

function KpiCard({ label, value, delta, icon, positive, extraClass = "" }: KpiCardProps) {
  return (
    <div className={`bg-surface-container-lowest rounded-xl border border-outline-variant p-5 flex flex-col gap-3 ${extraClass}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-on-surface-variant">{label}</span>
        <span className="material-symbols-outlined text-[20px] text-on-surface-variant">{icon}</span>
      </div>
      <p className="font-headline text-3xl font-bold text-on-surface">{value}</p>
      <p className={`text-xs font-medium ${positive ? "text-[#1a7f4b]" : "text-error"}`}>
        {delta}
      </p>
    </div>
  )
}

function FeedQualityScore() {
  const overall = 73
  const circumference = 2 * Math.PI * 36
  const offset = circumference - (overall / 100) * circumference
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-5">
      <p className="text-sm font-semibold text-on-surface mb-4">Feed Quality Score</p>
      <div className="flex items-center gap-6">
        <div className="relative w-24 h-24 shrink-0">
          <svg viewBox="0 0 80 80" className="w-24 h-24 -rotate-90">
            <circle cx="40" cy="40" r="36" fill="none" stroke="#e5e2de" strokeWidth="8" />
            <circle cx="40" cy="40" r="36" fill="none" stroke="#072078" strokeWidth="8"
              strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-headline text-2xl font-bold text-primary">{overall}</span>
            <span className="text-[10px] text-on-surface-variant">/ 100</span>
          </div>
        </div>
        <div className="flex-1 space-y-2">
          {[
            { label: "Completeness", value: 82 },
            { label: "Accuracy", value: 71 },
            { label: "Richness", value: 64 },
          ].map(({ label, value }) => (
            <div key={label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-on-surface-variant">{label}</span>
                <span className="font-semibold text-on-surface">{value}%</span>
              </div>
              <div className="h-1.5 bg-surface-container-high rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${value}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function RecentActivity({ products, loading }: { products: CatalogProduct[]; loading: boolean }) {
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-5 h-full">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold text-on-surface">Recent Activity</p>
      </div>
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 rounded-lg bg-surface-container animate-pulse" />
          ))}
        </div>
      ) : products.length === 0 ? (
        <p className="text-sm text-on-surface-variant text-center py-8">Inga produkter ännu</p>
      ) : (
        <div className="space-y-3">
          {products.map((p) => {
            const key = productStatusKey(p.status)
            return (
              <div key={p.sku_id} className="flex items-start gap-3 pb-3 border-b border-outline-variant last:border-0 last:pb-0">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-on-surface truncate">{p.title ?? "—"}</p>
                  <p className="text-xs text-on-surface-variant mt-0.5">{p.sku_id}</p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge(key)}`}>
                    {statusLabel(key)}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {p.overall_score != null && (
                      <span className={`text-xs font-bold ${scoreColor(p.overall_score)}`}>{p.overall_score}</span>
                    )}
                    <span className="text-[10px] text-on-surface-variant">{relativeTime(p.enriched_at)}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const tabs = ["Overview", "Library"]

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("Overview")

  // Health
  const [healthOnline, setHealthOnline] = useState<boolean | undefined>(undefined)

  // Stats
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState(false)

  // Recent activity
  const [recentProducts, setRecentProducts] = useState<CatalogProduct[]>([])
  const [activityLoading, setActivityLoading] = useState(true)

  // Upload
  const [showUpload, setShowUpload] = useState(false)

  // Bulk enrichment
  const [bulkJobId, setBulkJobId] = useState<string | null>(null)
  const [bulkProgress, setBulkProgress] = useState(0)
  const [bulkStatus, setBulkStatus] = useState<BulkStatus>("idle")

  // ── Recent activity fetcher ───────────────────────────────────────────────
  const fetchRecentActivity = useCallback(async () => {
    setActivityLoading(true)
    try {
      const { data } = await api.get<CatalogResponse>("/api/v1/catalog", {
        params: { page_size: 6 },
      })
      setRecentProducts(data.products)
    } catch {
      // non-critical — silent fail
    } finally {
      setActivityLoading(false)
    }
  }, [])

  // ── STEG 6: fetchStats helper ──────────────────────────────────────────────
  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const { data } = await api.get<StatsResponse>("/api/v1/stats")
      setStats(data)
      setStatsError(false)
    } catch {
      setStatsError(true)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  // ── STEG 2: Health check on mount ─────────────────────────────────────────
  useEffect(() => {
    api.get("/api/v1/health")
      .then(() => setHealthOnline(true))
      .catch(() => setHealthOnline(false))
  }, [])

  // ── STEG 3: Stats + activity on mount, auto-refresh every 10s ───────────
  useEffect(() => {
    fetchStats()
    fetchRecentActivity()
    const interval = setInterval(fetchStats, 10_000)
    return () => clearInterval(interval)
  }, [fetchStats, fetchRecentActivity])

  // ── STEG 5: Bulk job polling ──────────────────────────────────────────────
  useEffect(() => {
    if (!bulkJobId) return

    const interval = setInterval(async () => {
      try {
        const { data } = await api.get<JobResponse>(`/api/v1/jobs/${bulkJobId}`)
        setBulkProgress(data.progress_pct)

        if (data.status === "complete" || data.status === "completed") {
          clearInterval(interval)
          setBulkStatus("complete")
          setBulkJobId(null)
          fetchStats()
        } else if (data.status === "failed") {
          clearInterval(interval)
          setBulkStatus("failed")
          setBulkJobId(null)
        }
      } catch {
        clearInterval(interval)
        setBulkStatus("failed")
        setBulkJobId(null)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [bulkJobId, fetchStats])

  // ── Bulk enrich handler ───────────────────────────────────────────────────
  async function handleEnrichAll() {
    if (bulkStatus === "processing") return
    setBulkStatus("processing")
    setBulkProgress(0)
    try {
      const { data } = await api.post<BulkEnrichResponse>("/api/v1/enrich/bulk", { limit: 10 })
      setBulkJobId(data.job_id)
    } catch {
      setBulkStatus("failed")
    }
  }

  // ── KPI data from stats ───────────────────────────────────────────────────
  const returnRiskPct = stats && stats.total_products > 0
    ? ((stats.return_risk_high / stats.total_products) * 100).toFixed(1)
    : "0"

  const kpiCards: KpiCardProps[] = stats
    ? [
        {
          label: "Total SKUs",
          value: stats.total_products.toLocaleString(),
          delta: `${stats.enrichment_rate}% enriched`,
          icon: "inventory_2",
          positive: true,
        },
        {
          label: "Enriched",
          value: stats.enriched.toLocaleString(),
          delta: `${stats.enrichment_rate}% of catalog`,
          icon: "auto_awesome",
          positive: true,
        },
        {
          label: "Needs attention",
          value: stats.needs_attention.toLocaleString(),
          delta: "Not yet enriched",
          icon: "warning",
          positive: false,
          extraClass: "border-l-2 border-amber-400",
        },
        {
          label: "Return risk high",
          value: stats.return_risk_high.toLocaleString(),
          delta: `${returnRiskPct}% of catalog`,
          icon: "assignment_return",
          positive: false,
          extraClass: "border-l-2 border-error bg-error-container/30",
        },
      ]
    : []

  const errorKpis: KpiCardProps[] = [
    { label: "Total SKUs", value: "-", delta: "—", icon: "inventory_2", positive: true },
    { label: "Enriched", value: "-", delta: "—", icon: "auto_awesome", positive: true },
    { label: "Needs attention", value: "-", delta: "—", icon: "warning", positive: false, extraClass: "border-l-2 border-amber-400" },
    { label: "Return risk high", value: "-", delta: "—", icon: "assignment_return", positive: false, extraClass: "border-l-2 border-error bg-error-container/30" },
  ]

  return (
    <div className="min-h-full bg-background">
      {/* TopNav */}
      <header className="bg-surface-container-lowest border-b border-outline-variant px-8 pt-5 pb-0">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                  activeTab === tab
                    ? "border-primary text-primary"
                    : "border-transparent text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {tab}
              </button>
            ))}
            <Link
              href="/processing"
              className="px-4 py-2 text-sm font-medium border-b-2 border-transparent text-on-surface-variant hover:text-on-surface transition-colors -mb-px"
            >
              Batch Processing
            </Link>
          </div>
          <div className="flex items-center gap-3">
            {/* Health indicator */}
            {healthOnline !== undefined && (
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${healthOnline ? "bg-[#1a7f4b]" : "bg-error"}`} />
                <span className="text-xs text-on-surface-variant">
                  {healthOnline ? "Online" : "Offline"}
                </span>
              </div>
            )}
            <button className="relative p-2 rounded-xl hover:bg-surface-container transition-colors">
              <span className="material-symbols-outlined text-[20px] text-on-surface-variant">notifications</span>
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full" />
            </button>
            <button className="p-2 rounded-xl hover:bg-surface-container transition-colors">
              <span className="material-symbols-outlined text-[20px] text-on-surface-variant">settings</span>
            </button>
            <div className="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center">
              <span className="text-xs font-bold text-white">AD</span>
            </div>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div className="px-8 py-6 border-b border-outline-variant bg-surface-container-lowest">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="font-headline text-3xl font-bold text-on-surface">Editorial Hub</h1>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl border border-outline-variant text-on-surface hover:bg-surface-container transition-colors">
              <span className="material-symbols-outlined text-[16px]">download</span>
              Export
            </button>
            <button
              onClick={handleEnrichAll}
              disabled={bulkStatus === "processing"}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl bg-primary text-white hover:bg-primary-container transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
              {enrichButtonLabel(bulkStatus, bulkProgress)}
            </button>
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl border border-outline-variant text-on-surface hover:bg-surface-container transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">upload</span>
              Upload
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-8 py-6 space-y-6">
        {/* KPI row */}
        <div className="grid grid-cols-4 gap-4">
          {statsLoading ? (
            Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} rows={2} />)
          ) : statsError ? (
            errorKpis.map((kpi) => <KpiCard key={kpi.label} {...kpi} />)
          ) : (
            kpiCards.map((kpi) => <KpiCard key={kpi.label} {...kpi} />)
          )}
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8">
            <FeedQualityScore />
            {/* ConfidenceTrend + EnrichmentByCategory hidden — awaiting backend aggregation endpoints */}
          </div>
          <div className="col-span-4">
            <RecentActivity products={recentProducts} loading={activityLoading} />
          </div>
        </div>
      </div>

      {/* Upload modal */}
      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onSuccess={() => {
          setShowUpload(false)
          fetchStats()
        }}
      />
    </div>
  )
}
