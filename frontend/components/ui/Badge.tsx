interface BadgeProps {
  score?: number
  severity?: "high" | "medium" | "low"
  label?: string
  className?: string
}

function severityFromScore(score: number): "high" | "medium" | "low" {
  if (score >= 80) return "low"
  if (score >= 50) return "medium"
  return "high"
}

const severityStyles = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-error-container text-error",
}

export function Badge({ score, severity, label, className = "" }: BadgeProps) {
  const level = severity ?? (score !== undefined ? severityFromScore(score) : "medium")
  const text = label ?? (score !== undefined ? `${score}` : level)

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${severityStyles[level]} ${className}`}
    >
      {text}
    </span>
  )
}
