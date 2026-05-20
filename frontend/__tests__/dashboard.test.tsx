import React from "react"
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react"
import DashboardPage from "@/app/dashboard/page"
import { api } from "@/lib/api"

jest.mock("@/lib/api", () => ({
  api: {
    get: jest.fn(),
    post: jest.fn(),
  },
}))

jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
    className,
  }: {
    href: string
    children: React.ReactNode
    className?: string
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  )
  MockLink.displayName = "MockLink"
  return MockLink
})

const mockApi = api as jest.Mocked<typeof api>

function mockStats(overrides: Partial<{
  total_products: number
  enriched: number
  pending: number
  failed: number
  needs_attention: number
  return_risk_high: number
  enrichment_rate: number
  avg_enrichment_score: number | null
}> = {}) {
  const stats = {
    total_products: 26,
    enriched: 6,
    pending: 20,
    failed: 0,
    needs_attention: 20,
    return_risk_high: 20,
    enrichment_rate: 23.1,
    avg_enrichment_score: null,
    ...overrides,
  }
  mockApi.get.mockImplementation((url: string) => {
    if (url === "/api/v1/stats") return Promise.resolve({ data: stats }) as never
    if (url === "/api/v1/health") return Promise.resolve({ data: {} }) as never
    if (url === "/api/v1/catalog") return Promise.resolve({ data: { products: [], total: 0, page: 1, page_size: 6 } }) as never
    return Promise.resolve({ data: {} }) as never
  })
}

beforeEach(() => {
  jest.clearAllMocks()
  mockStats()
})

// ── Existing tests ────────────────────────────────────────────────────────────

describe("DashboardPage — Batch Processing-länk", () => {
  it("Batch Processing är en länk med href='/processing'", async () => {
    render(<DashboardPage />)

    const link = await screen.findByRole("link", { name: /Batch Processing/i })
    expect(link).toHaveAttribute("href", "/processing")
  })
})

describe("DashboardPage — return risk percentage", () => {
  it("visar return risk som procent av total_products, inte enriched", async () => {
    mockStats({ total_products: 26, enriched: 6, return_risk_high: 20 })

    render(<DashboardPage />)

    // 20 / 26 * 100 = 76.9%
    await screen.findByText(/76\.9%/)
    expect(screen.queryByText(/333/)).not.toBeInTheDocument()
  })

  it("visar 0% of catalog om total_products är 0", async () => {
    mockStats({ total_products: 0, enriched: 0, return_risk_high: 0 })

    render(<DashboardPage />)

    await screen.findByText("0% of catalog")
  })
})

// ── FEED-073: Preflight flow ──────────────────────────────────────────────────

const MOCK_PREFLIGHT = {
  product_count: 5,
  estimated_ai_calls: 5,
  estimated_input_tokens: 6000,
  estimated_output_tokens: 2500,
  estimated_total_tokens: 8500,
  estimated_cost_usd: 0.0225,
  fields_to_enrich: { brand: 3, description: 5 },
  tool_plan: { rag: true, web_search: false, image_analysis: false },
  requires_confirmation: true,
}

const MOCK_BULK_RESPONSE = { job_id: "job-abc-123", status: "queued" }

// Overrides the get mock to also handle /api/v1/jobs/* for polling tests.
function mockWithJobPolling(jobData: {
  status: string
  progress_pct: number
  processed: number
  total: number
  failed: number
}) {
  mockApi.get.mockImplementation((url: string) => {
    if (url === "/api/v1/stats") return Promise.resolve({ data: { total_products: 26, enriched: 6, pending: 20, failed: 0, needs_attention: 20, return_risk_high: 20, enrichment_rate: 23.1, avg_enrichment_score: null } }) as never
    if (url === "/api/v1/health") return Promise.resolve({ data: {} }) as never
    if (url === "/api/v1/catalog") return Promise.resolve({ data: { products: [], total: 0, page: 1, page_size: 6 } }) as never
    if (url.startsWith("/api/v1/jobs/")) return Promise.resolve({ data: { job_id: "job-abc-123", ...jobData } }) as never
    return Promise.resolve({ data: {} }) as never
  })
}

// Clicks "Enrich all", waits for the preflight modal, then clicks "Bekräfta".
// Caller must set up post mocks for preflight and bulk before calling this.
async function clickEnrichAllAndConfirm() {
  mockApi.post
    .mockResolvedValueOnce({ data: MOCK_PREFLIGHT })
    .mockResolvedValueOnce({ data: MOCK_BULK_RESPONSE })

  const btn = await screen.findByRole("button", { name: /Enrich all/i })
  fireEvent.click(btn)
  const confirmBtn = await screen.findByRole("button", { name: /Bekräfta/i })
  fireEvent.click(confirmBtn)
}

describe("DashboardPage — Preflight flow", () => {
  it('"Enrich all" anropar preflight-endpoint, inte bulk direkt', async () => {
    mockApi.post.mockResolvedValueOnce({ data: MOCK_PREFLIGHT })
    render(<DashboardPage />)

    const btn = await screen.findByRole("button", { name: /Enrich all/i })
    fireEvent.click(btn)

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith(
        "/api/v1/enrich/preflight",
        { limit: 10 }
      )
    })
    expect(mockApi.post).not.toHaveBeenCalledWith(
      "/api/v1/enrich/bulk",
      expect.anything()
    )
  })

  it("PreflightModal visas med product_count, tokens och kostnad", async () => {
    mockApi.post.mockResolvedValueOnce({ data: MOCK_PREFLIGHT })
    render(<DashboardPage />)

    const btn = await screen.findByRole("button", { name: /Enrich all/i })
    fireEvent.click(btn)

    // Modal must render with the three key values from the preflight response.
    await screen.findByRole("button", { name: /Bekräfta/i })
    expect(screen.getByText(/5 produkter/)).toBeInTheDocument()
    expect(screen.getByText(/8\s?500/)).toBeInTheDocument()
    expect(screen.getByText(/0\.0225/)).toBeInTheDocument()
  })

  it('"Bekräfta" anropar POST /enrich/bulk', async () => {
    render(<DashboardPage />)
    await clickEnrichAllAndConfirm()

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith(
        "/api/v1/enrich/bulk",
        { limit: 10 }
      )
    })
  })

  it('"Avbryt" anropar inte /enrich/bulk och återställer knappen till idle', async () => {
    mockApi.post.mockResolvedValueOnce({ data: MOCK_PREFLIGHT })
    render(<DashboardPage />)

    const btn = await screen.findByRole("button", { name: /Enrich all/i })
    fireEvent.click(btn)

    const cancelBtn = await screen.findByRole("button", { name: /Avbryt/i })
    fireEvent.click(cancelBtn)

    expect(mockApi.post).not.toHaveBeenCalledWith(
      "/api/v1/enrich/bulk",
      expect.anything()
    )
    // Button label must return to idle state.
    await screen.findByRole("button", { name: /Enrich all/i })
  })
})

// ── FEED-073: Enrichment progressbar ─────────────────────────────────────────

describe("DashboardPage — Enrichment progressbar", () => {
  beforeEach(() => {
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it("progressbar visas med korrekt fill och räknare under processing", async () => {
    mockWithJobPolling({
      status: "running",
      progress_pct: 45,
      processed: 12,
      total: 26,
      failed: 0,
    })
    render(<DashboardPage />)
    await clickEnrichAllAndConfirm()

    // Advance past the 3-second polling interval.
    await act(async () => {
      jest.advanceTimersByTime(3001)
    })

    // Fill element must reflect progress_pct from the job response.
    // Implementation must set data-testid="enrich-progress-fill" on the fill div.
    expect(screen.getByTestId("enrich-progress-fill")).toHaveStyle("width: 45%")
    expect(screen.getByText(/12/)).toBeInTheDocument()
    expect(screen.getByText(/26/)).toBeInTheDocument()
  })

  it("completed-state visar grön bekräftelse och döljer progressbar-filen", async () => {
    mockWithJobPolling({
      status: "completed",
      progress_pct: 100,
      processed: 26,
      total: 26,
      failed: 0,
    })
    render(<DashboardPage />)
    await clickEnrichAllAndConfirm()

    await act(async () => {
      jest.advanceTimersByTime(3001)
    })

    expect(screen.getByText(/✓ Klart/)).toBeInTheDocument()
    expect(screen.getByText(/26\/26/)).toBeInTheDocument()
    expect(screen.queryByTestId("enrich-progress-fill")).not.toBeInTheDocument()
  })

  it("failed-state visar röd felbeskrivning med antal misslyckade och döljer progressbar-filen", async () => {
    mockWithJobPolling({
      status: "failed",
      progress_pct: 50,
      processed: 13,
      total: 26,
      failed: 3,
    })
    render(<DashboardPage />)
    await clickEnrichAllAndConfirm()

    await act(async () => {
      jest.advanceTimersByTime(3001)
    })

    expect(screen.getByText(/Fel/)).toBeInTheDocument()
    expect(screen.getByText(/3 produkter/)).toBeInTheDocument()
    expect(screen.queryByTestId("enrich-progress-fill")).not.toBeInTheDocument()
  })
})
