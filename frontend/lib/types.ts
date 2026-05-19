export interface CatalogProduct {
  sku_id: string
  title: string | null
  category: string | null
  brand: string | null
  price: number | null
  status: "enriched" | "needs_review" | "return_risk"
  overall_score: number | null
  return_risk: string | null
  enriched_at: string | null
}

export interface CatalogResponse {
  total: number
  page: number
  page_size: number
  products: CatalogProduct[]
}

export interface Product {
  id: number
  sku_id: string
  title: string | null
  description: string | null
  brand: string | null
  category: string | null
  price: number | null
  attributes: Record<string, string>
  quality_warnings: QualityWarning[]
  feed_source: string
  detected_source: string
}

export interface QualityWarning {
  field: string
  severity: "high" | "medium" | "low"
  message: string
}

export interface AnalysisResult {
  id: number
  sku_id: string
  overall_score: number
  enriched_fields: Record<string, EnrichedField>
  issues: Issue[]
  return_risk: "high" | "medium" | "low"
  return_risk_reason: string
  action_items: string[]
  prompt_version: string
  total_tokens: number
  created_at: string
}

export interface EnrichedField {
  reasoning: string
  confidence: number
  suggested_value: string
}

export interface Issue {
  field: string
  severity: "high" | "medium" | "low"
  problem: string
  suggestion: string
}

export interface Job {
  id: string
  job_type: string
  status: "queued" | "running" | "completed" | "failed"
  total: number
  processed: number
  failed: number
  progress_pct: number
  estimated_seconds_remaining: number | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface StatsResponse {
  total_products: number
  enriched: number
  pending: number
  failed: number
  needs_attention: number
  return_risk_high: number
  enrichment_rate: number
  avg_enrichment_score: number | null
}

export interface JobResponse {
  job_id: string
  status: "queued" | "processing" | "running" | "complete" | "completed" | "failed"
  progress_pct: number
  processed?: number
  total?: number
  failed?: number
  eta_seconds?: number
}

export interface IngestResponse {
  message: string
  products_imported?: number
}

export interface BulkEnrichResponse {
  job_id: string
  status: string
}

export interface PreflightResponse {
  product_count: number
  estimated_ai_calls: number
  estimated_input_tokens: number
  estimated_output_tokens: number
  estimated_total_tokens: number
  estimated_cost_usd: number
  fields_to_enrich: Record<string, number>
  tool_plan: Record<string, boolean>
  requires_confirmation: boolean
}

export interface SuggestedEnrichment {
  field: string
  current_value: string | null
  suggested_value: string
  reasoning: string
}

export interface ImageAnalysisResult {
  sku_id: string
  image_quality_score: number
  detected_attributes: Record<string, string>
  quality_issues: string[]
  suggested_enrichments: SuggestedEnrichment[]
  overall_confidence: number
  reasoning: string
  total_tokens: number
}

export interface EnrichmentDetail {
  field: string
  suggested_value: string
  reasoning: string
  confidence: number
}

export interface IssueDetail {
  field: string
  severity: "high" | "medium" | "low"
  problem: string
  suggestion: string
}

export interface ProductDetailResponse {
  sku_id: string
  title: string | null
  description: string | null
  category: string | null
  brand: string | null
  price: number | null
  feed_source: string | null
  detected_source: string | null
  attributes: Record<string, string>
  overall_score: number | null
  return_risk: string | null
  return_risk_reason: string | null
  action_items: string[]
  issues: IssueDetail[]
  enriched_fields: EnrichmentDetail[]
  enriched_at: string | null
  prompt_version: string | null
  total_tokens: number | null
  image_url: string | null
}

export interface EnrichResponse {
  sku_id: string
  analysis_id: number
  overall_score: number | null
  return_risk: string | null
  enrichment_priority: string
  total_tokens: number | null
}

export interface JobListItem {
  id: string
  job_type: string
  status: string
  total: number
  processed: number
  failed: number
  progress_pct: number
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface ProductVariant {
  id: number
  sku_id: string
  ean: string | null
  color: string | null
  size: string | null
  seo_title: string | null
  seo_description: string | null
  search_keywords: string[]
  ai_search_snippet: string | null
  enriched_at: string | null
}
