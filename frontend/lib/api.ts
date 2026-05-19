import axios, { AxiosRequestConfig } from "axios"

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8010"

const client = axios.create({ baseURL: BACKEND_URL })

export const api = {
  // ── Generic methods (used by dashboard and other pages) ───────────────────
  get: <T>(url: string, config?: AxiosRequestConfig) =>
    client.get<T>(url, config),

  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    client.post<T>(url, data, config),

  patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    client.patch<T>(url, data, config),

  // ── Named helpers (used by other pages) ───────────────────────────────────
  getProducts: (params?: {
    limit?: number
    offset?: number
    category?: string
    return_risk?: string
  }) => client.get("/api/v1/products", { params }),

  getProduct: (sku_id: string) =>
    client.get(`/api/v1/products/${sku_id}`),

  enrichProductSingle: (sku_id: string) =>
    client.post(`/api/v1/products/${sku_id}/enrich`),

  enrichProduct: (sku_id: string) =>
    client.post(`/api/v1/enrich/${sku_id}`),

  enrichBulk: (limit: number) =>
    client.post("/api/v1/enrich/bulk", { limit }),

  getJob: (job_id: string) =>
    client.get(`/api/v1/jobs/${job_id}`),

  getVariants: (sku_id: string) =>
    client.get(`/api/v1/variants/${sku_id}`),

  ingestCSV: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return client.post("/api/v1/ingest/csv?feed_source=auto", form)
  },

  ingestXLSX: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return client.post("/api/v1/ingest/xlsx?feed_source=auto", form)
  },
}
