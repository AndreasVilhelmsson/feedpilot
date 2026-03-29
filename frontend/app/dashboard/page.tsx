"use client"

import { useState, useEffect, useCallback } from "react"
import { api } from "@/lib/api"
import type { StatsResponse, JobResponse, BulkEnrichResponse } from "@/lib/types"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { UploadModal } from "@/components/ui/UploadModal"

// ── Static chart/activity data ───────────────────────────────────────────────

const confidenceTrend = [62, 65, 68, 71, 69, 74, 78, 76, 81, 83, 85, 84]
const trendLabels = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

const categoryScores = [
  { name: "Electronics", score: 87, count: 423 },
  { name: "Clothing", score: 72, count: 891 },
  { name: "Home & Garden", score: 65, count: 312 },
  { name: "Sports", score: 58, count: 187 },
  { name: "Beauty", score: 44, count: 234 },
]

const recentActivity = [
  { sku: "SKU-4821", title: "Wireless Noise-Cancelling Headphones", score: 94, time: "2 min ago", status: "success" },
  { sku: "SKU-3307", title: "Organic Cotton T-Shirt", score: 61, time: "8 min ago", status: "warning" },
  { sku: "SKU-9102", title: "Running Shoes Pro X", score: 38, time: "15 min ago", status: "error" },
  { sku: "SKU-2244", title: "Kitchen Knife Set", score: 88, time: "23 min ago", status: "success" },
  { sku: "SKU-5519", title: "Yoga Mat Premium", score: 79, time: "31 min ago", status: "success" },
  { sku: "SKU-7731", title: "LED Desk Lamp", score: 55, time: "45 min ago", status: "warning" },
]

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

// ── Chart ─────────────────────────────────────────────────────────────────────

function TrendBars() {
  const max = Math.max(...confidenceTrend)
  return (
    <div className="flex items-end gap-1 h-20">
      {confidenceTrend.map((v, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full rounded-lg bg-primary opacity-80"
            style={{ height: `${(v / max) * 80}px` }}
          />
          <span className="text-[9px] text-on-surface-variant">{trendLabels[i]}</span>
        </div>
      ))}
    </div>
  )
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

function ConfidenceTrend() {
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold text-on-surface">AI Confidence Trend</p>
        <span className="text-xs text-on-surface-variant">Last 12 months</span>
      </div>
      <TrendBars />
      <div className="mt-3 flex items-center gap-2">
        <span className="text-2xl font-headline font-bold text-primary">84%</span>
        <span className="text-xs text-[#1a7f4b] font-medium">↑ +3.2% vs last month</span>
      </div>
    </div>
  )
}

function EnrichmentByCategory() {
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-5">
      <p className="text-sm font-semibold text-on-surface mb-4">Enrichment by Category</p>
      <div className="space-y-3">
        {categoryScores.map(({ name, score, count }) => (
          <div key={name}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-on-surface">{name}</span>
              <div className="flex items-center gap-3">
                <span className="text-on-surface-variant">{count} SKUs</span>
                <span className={`font-semibold w-7 text-right ${scoreColor(score)}`}>{score}</span>
              </div>
            </div>
            <div className="h-2 bg-surface-container-high rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${score >= 75 ? "bg-[#1a7f4b]" : score >= 50 ? "bg-tertiary-fixed-dim" : "bg-error"}`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RecentActivity() {
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-5 h-full">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold text-on-surface">Recent Activity</p>
        <button className="text-xs text-primary font-medium hover:underline">View all</button>
      </div>
      <div className="space-y-3">
        {recentActivity.map((item) => (
          <div key={item.sku} className="flex items-start gap-3 pb-3 border-b border-outline-variant last:border-0 last:pb-0">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-on-surface truncate">{item.title}</p>
              <p className="text-xs text-on-surface-variant mt-0.5">{item.sku}</p>
            </div>
            <div className="flex flex-col items-end gap-1 shrink-0">
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge(item.status)}`}>
                {statusLabel(item.status)}
              </span>
              <div className="flex items-center gap-1.5">
                <span className={`text-xs font-bold ${scoreColor(item.score)}`}>{item.score}</span>
                <span className="text-[10px] text-on-surface-variant">{item.time}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const tabs = ["Overview", "Batch Processing", "Library"]

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("Overview")

  // Health
  const [healthOnline, setHealthOnline] = useState<boolean | undefined>(undefined)

  // Stats
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState(false)

  // Upload
  const [showUpload, setShowUpload] = useState(false)

  // Bulk enrichment
  const [bulkJobId, setBulkJobId] = useState<string | null>(null)
  const [bulkProgress, setBulkProgress] = useState(0)
  const [bulkStatus, setBulkStatus] = useState<BulkStatus>("idle")

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

  // ── STEG 3: Stats on mount ────────────────────────────────────────────────
  useEffect(() => {
    fetchStats()
  }, [fetchStats])

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
  const kpiCards: KpiCardProps[] = stats
    ? [
        {
          label: "Total SKUs",
          value: stats.total_products.toLocaleString(),
          delta: "+124 this week",
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
          value: stats.pending.toLocaleString(),
          delta: "↓ 38 since yesterday",
          icon: "warning",
          positive: false,
          extraClass: "border-l-2 border-amber-400",
        },
        {
          label: "Return risk high",
          value: stats.failed.toLocaleString(),
          delta: "3.1% of enriched",
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
          <div className="col-span-8 space-y-4">
            <FeedQualityScore />
            <ConfidenceTrend />
            <EnrichmentByCategory />
          </div>
          <div className="col-span-4">
            <RecentActivity />
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
