export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="bg-surface-container-low rounded-xl p-5 animate-pulse">
      <div className="h-4 bg-surface-container-highest rounded w-3/4 mb-4" />
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-3 bg-surface-container-high rounded mb-2"
          style={{ width: `${70 + (i % 3) * 10}%` }}
        />
      ))}
    </div>
  )
}
