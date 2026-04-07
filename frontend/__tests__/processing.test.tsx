import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import ProcessingPage from "@/app/processing/page"
import { api } from "@/lib/api"

jest.mock("@/lib/api", () => ({
  api: {
    get: jest.fn(),
    post: jest.fn(),
  },
}))

const mockApi = api as jest.Mocked<typeof api>

const statsResponse = {
  total_products: 26,
  enriched: 5,
  pending: 21,
  failed: 21,
  needs_attention: 21,
  return_risk_high: 20,
  enrichment_rate: 19.2,
}

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()

  mockApi.get.mockImplementation((url: string) => {
    if (url === "/api/v1/stats") return Promise.resolve({ data: statsResponse }) as never
    if (url.startsWith("/api/v1/jobs")) return Promise.resolve({ data: [] }) as never
    return Promise.resolve({ data: {} }) as never
  })
})

describe("ProcessingPage — handleStartBatch", () => {
  it("anropar POST /api/v1/enrich/bulk när Start enrichment klickas i modalen", async () => {
    mockApi.post.mockResolvedValue({ data: { job_id: "test-123", status: "queued" } } as never)

    render(<ProcessingPage />)

    fireEvent.click(screen.getByRole("button", { name: /New Batch/i }))
    expect(screen.getByText("Start new batch")).toBeInTheDocument()

    const startButtons = screen.getAllByRole("button", { name: /Start enrichment/i })
    fireEvent.click(startButtons[startButtons.length - 1])

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith(
        "/api/v1/enrich/bulk",
        expect.objectContaining({ limit: expect.any(Number) })
      )
    })
  })

  it("visar felmeddelande om POST /api/v1/enrich/bulk misslyckas", async () => {
    mockApi.post.mockRejectedValue(new Error("Server error"))

    render(<ProcessingPage />)

    fireEvent.click(screen.getByRole("button", { name: /New Batch/i }))

    const startButtons = screen.getAllByRole("button", { name: /Start enrichment/i })
    fireEvent.click(startButtons[startButtons.length - 1])

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument()
    })
  })

  it("stänger felmeddelande när ✕ klickas", async () => {
    mockApi.post.mockRejectedValue(new Error("Server error"))

    render(<ProcessingPage />)

    fireEvent.click(screen.getByRole("button", { name: /New Batch/i }))
    const startButtons = screen.getAllByRole("button", { name: /Start enrichment/i })
    fireEvent.click(startButtons[startButtons.length - 1])

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument())

    fireEvent.click(screen.getByRole("alert").querySelector("button")!)
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("sparar job_id i localStorage efter lyckad POST", async () => {
    mockApi.post.mockResolvedValue({ data: { job_id: "abc-999", status: "queued" } } as never)

    render(<ProcessingPage />)

    fireEvent.click(screen.getByRole("button", { name: /New Batch/i }))
    const startButtons = screen.getAllByRole("button", { name: /Start enrichment/i })
    fireEvent.click(startButtons[startButtons.length - 1])

    await waitFor(() => {
      expect(localStorage.getItem("fp_active_job_id")).toBe("abc-999")
    })
  })
})
