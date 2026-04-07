import React from "react"
import { render, screen } from "@testing-library/react"
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
}> = {}) {
  const stats = {
    total_products: 26,
    enriched: 6,
    pending: 20,
    failed: 0,
    needs_attention: 20,
    return_risk_high: 20,
    enrichment_rate: 23.1,
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
