"use client"

interface Tab {
  label: string
  value: string
}

interface TopNavProps {
  title: string
  tabs?: Tab[]
  activeTab?: string
  onTabChange?: (value: string) => void
  actions?: React.ReactNode
  healthOnline?: boolean
}

export function TopNav({
  title,
  tabs,
  activeTab,
  onTabChange,
  actions,
  healthOnline,
}: TopNavProps) {
  return (
    <header className="bg-surface border-b border-outline-variant px-8 pt-6 pb-0">
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-display text-2xl font-bold text-on-surface">
          {title}
        </h1>
        <div className="flex items-center gap-4">
          {healthOnline !== undefined && (
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  healthOnline ? "bg-[#1a7f4b]" : "bg-error"
                }`}
              />
              <span className="text-xs text-on-surface-variant">
                {healthOnline ? "Online" : "Offline"}
              </span>
            </div>
          )}
          {actions && <div className="flex items-center gap-3">{actions}</div>}
        </div>
      </div>

      {tabs && (
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => onTabChange?.(tab.value)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.value
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}
    </header>
  )
}
