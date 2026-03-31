"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import type { CatalogProduct, CatalogResponse } from "@/lib/types"

// ── Types ────────────────────────────────────────────────────────────────────

type StatusFilter = "all" | "enriched" | "needs_review" | "return_risk"

// ── Helpers ──────────────────────────────────────────────────────────────────

const statusConfig: Record<
  CatalogProduct["status"],
  { label: string; className: string }
> = {
  enriched: {
    label: "Enriched",
    className: "bg-[#dcf5e8] text-[#1a7f4b]",
  },
  needs_review: {
    label: "Needs review",
    className: "bg-surface-container-high text-on-surface-variant",
  },
  return_risk: {
    label: "Return risk",
    className: "bg-error-container text-on-error-container",
  },
}

function scoreClass(score: number): string {
  if (score >= 80) return "border-[#1a7f4b] text-[#1a7f4b]"
  if (score >= 50) return "border-tertiary-fixed-dim text-tertiary"
  return "border-error text-error"
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ScoreCircle({ score }: { score: number | null }) {
  if (score === null)
    return <span className="text-sm text-on-surface-variant">—</span>
  return (
    <div
      className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-xs font-bold shrink-0 ${scoreClass(score)}`}
    >
      {score}
    </div>
  )
}

function StatusBadge({ status }: { status: CatalogProduct["status"] }) {
  const { label, className } = statusConfig[status]
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${className}`}
    >
      {label}
    </span>
  )
}

function TableSkeleton() {
  return (
    <tbody>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} className="border-b border-outline-variant animate-pulse">
          <td className="px-4 py-3 w-10">
            <div className="w-4 h-4 bg-surface-container-high rounded" />
          </td>
          <td className="px-4 py-3">
            <div className="h-3 w-20 bg-surface-container-high rounded" />
          </td>
          <td className="px-4 py-3">
            <div className="h-3 w-40 bg-surface-container-high rounded mb-1" />
            <div className="h-2 w-24 bg-surface-container rounded" />
          </td>
          <td className="px-4 py-3">
            <div className="h-5 w-20 bg-surface-container-high rounded-full" />
          </td>
          <td className="px-4 py-3">
            <div className="w-9 h-9 bg-surface-container-high rounded-full" />
          </td>
          <td className="px-4 py-3">
            <div className="h-3 w-24 bg-surface-container-high rounded" />
          </td>
        </tr>
      ))}
    </tbody>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "enriched", label: "Enriched" },
  { value: "needs_review", label: "Needs review" },
  { value: "return_risk", label: "Return risk" },
]

const PAGE_SIZE = 10

export default function CatalogPage() {
  const router = useRouter()

  const [products, setProducts] = useState<CatalogProduct[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [enrichingSkus, setEnrichingSkus] = useState<Set<string>>(new Set())
  const [enrichAllRunning, setEnrichAllRunning] = useState(false)

  // Debounce search input 300ms
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  function handleSearchChange(val: string) {
    setSearchQuery(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(val)
      setPage(1)
    }, 300)
  }

  const fetchProducts = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get<CatalogResponse>("/api/v1/catalog", {
        params: {
          page,
          page_size: PAGE_SIZE,
          status: statusFilter,
          search: debouncedSearch,
        },
      })
      setProducts(data.products)
      setTotal(data.total)
    } catch {
      setProducts([])
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter, debouncedSearch])

  useEffect(() => {
    fetchProducts()
  }, [fetchProducts])

  // Reset page when filter changes
  function handleFilterChange(f: StatusFilter) {
    setStatusFilter(f)
    setPage(1)
    setSelected(new Set())
  }

  function toggleSelect(skuId: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(skuId)) next.delete(skuId)
      else next.add(skuId)
      return next
    })
  }

  async function handleEnrichSingle(skuId: string) {
    setEnrichingSkus((prev) => new Set(prev).add(skuId))
    try {
      await api.post(`/api/v1/products/${skuId}/enrich`)
      await fetchProducts()
    } finally {
      setEnrichingSkus((prev) => {
        const next = new Set(prev)
        next.delete(skuId)
        return next
      })
    }
  }

  async function handleEnrichAll() {
    setEnrichAllRunning(true)
    try {
      await api.post("/api/v1/enrich/bulk", { limit: 50 })
      await fetchProducts()
    } finally {
      setEnrichAllRunning(false)
    }
  }

  function toggleSelectAll() {
    if (selected.size === products.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(products.map((p) => p.sku_id)))
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const to = Math.min(page * PAGE_SIZE, total)

  return (
    <div className="min-h-full bg-background">
      {/* Header */}
      <div className="bg-surface-container-lowest border-b border-outline-variant px-8 py-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-headline text-3xl font-bold text-on-surface">
              Product Catalog
            </h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              {loading ? "Laddar..." : `${total.toLocaleString()} produkter`}
            </p>
          </div>
          <div className="flex items-center gap-3 mt-1">
            {/* Search */}
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-[18px] text-on-surface-variant">
                search
              </span>
              <input
                type="text"
                placeholder="Sök SKU eller titel..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="pl-9 pr-4 py-2 text-sm bg-surface-container rounded-xl border border-outline-variant focus:outline-none focus:border-primary text-on-surface placeholder:text-on-surface-variant w-56 transition-colors"
              />
            </div>
            {/* Enrich all */}
            <button
              onClick={handleEnrichAll}
              disabled={enrichAllRunning}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl bg-primary text-white hover:bg-primary-container transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {enrichAllRunning ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
              )}
              {enrichAllRunning ? "Enriching…" : "Enrich all"}
            </button>
          </div>
        </div>

        {/* Status filter tabs */}
        <div className="flex gap-1 mt-5">
          {STATUS_TABS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => handleFilterChange(value)}
              className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
                statusFilter === value
                  ? "bg-primary text-white"
                  : "text-on-surface-variant hover:bg-surface-container"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="px-8 py-6">
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant bg-surface-container-low">
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={
                      products.length > 0 &&
                      selected.size === products.length
                    }
                    onChange={toggleSelectAll}
                    className="rounded accent-primary"
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  SKU
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  Product
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  Score
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>

            {loading ? (
              <TableSkeleton />
            ) : products.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={6} className="px-4 py-16 text-center">
                    <span className="material-symbols-outlined text-[48px] text-on-surface-variant block mb-3">
                      inventory_2
                    </span>
                    <p className="text-on-surface-variant font-medium">
                      Inga produkter hittades
                    </p>
                    <p className="text-xs text-on-surface-variant mt-1 opacity-60">
                      Prova att ändra filter eller sökterm
                    </p>
                  </td>
                </tr>
              </tbody>
            ) : (
              <tbody>
                {products.map((product) => (
                  <tr
                    key={product.sku_id}
                    onClick={() =>
                      router.push(`/products/${product.sku_id}`)
                    }
                    className="border-b border-outline-variant last:border-0 hover:bg-surface-container-low transition-colors cursor-pointer"
                  >
                    <td
                      className="px-4 py-3"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(product.sku_id)}
                        onChange={() => toggleSelect(product.sku_id)}
                        className="rounded accent-primary"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-on-surface-variant">
                        {product.sku_id}
                      </span>
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <p className="font-medium text-on-surface truncate">
                        {product.title ?? "—"}
                      </p>
                      {product.category && (
                        <p className="text-xs text-on-surface-variant mt-0.5">
                          {product.category}
                          {product.brand ? ` · ${product.brand}` : ""}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={product.status} />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreCircle score={product.overall_score} />
                    </td>
                    <td
                      className="px-4 py-3"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleEnrichSingle(product.sku_id)}
                          disabled={enrichingSkus.has(product.sku_id)}
                          className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {enrichingSkus.has(product.sku_id) ? (
                            <span className="w-3 h-3 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <span className="material-symbols-outlined text-[13px]">auto_awesome</span>
                          )}
                          Enrich
                        </button>
                        <button
                          onClick={() => router.push(`/products/${product.sku_id}`)}
                          className="text-xs font-medium text-on-surface-variant hover:text-on-surface flex items-center gap-0.5 transition-colors"
                        >
                          View
                          <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        </div>

        {/* Pagination */}
        {!loading && total > 0 && (
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-on-surface-variant">
              Showing{" "}
              <span className="font-medium text-on-surface">
                {from}–{to}
              </span>{" "}
              of{" "}
              <span className="font-medium text-on-surface">
                {total.toLocaleString()}
              </span>
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-xl border border-outline-variant text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container transition-colors"
              >
                <span className="material-symbols-outlined text-[16px]">
                  chevron_left
                </span>
                Prev
              </button>
              <span className="text-sm text-on-surface-variant px-2">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-xl border border-outline-variant text-on-surface disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-container transition-colors"
              >
                Next
                <span className="material-symbols-outlined text-[16px]">
                  chevron_right
                </span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
