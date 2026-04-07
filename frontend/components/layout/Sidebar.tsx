"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

const navItems = [
  { href: "/dashboard", icon: "dashboard", label: "Dashboard" },
  { href: "/processing", icon: "batch_prediction", label: "Processing" },
  { href: "/catalog", icon: "inventory_2", label: "Catalog" },
  { href: "/image-analysis", icon: "image_search", label: "Image Analysis" },
  { href: "/settings", icon: "settings", label: "Settings" },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex flex-col w-64 h-screen fixed left-0 top-0 z-50 bg-[#31302e] text-[#fcf9f5] shadow-2xl shadow-black/20 shrink-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-white text-sm">auto_awesome</span>
          </div>
          <div>
            <span className="font-headline text-xl font-bold tracking-tight">
              Feed<span className="text-primary-fixed-dim">Pilot</span>
            </span>
            <p className="text-[0.625rem] uppercase tracking-widest text-[#c5c5d3] opacity-60 mt-0.5">
              High-End Editorial
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, icon, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/")
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                active
                  ? "border-r-2 border-emerald-500 bg-[#e5e2de]/10 text-white"
                  : "opacity-70 hover:opacity-100 hover:bg-[#e5e2de]/5 text-white"
              }`}
            >
              <span className="material-symbols-outlined text-[20px]">
                {icon}
              </span>
              {label}
            </Link>
          )
        })}
      </nav>

      {/* New Analysis button + footer */}
      <div className="px-4 pb-4 space-y-3">
        <button className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-white text-sm font-semibold transition-opacity hover:opacity-90">
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Analysis
        </button>
        <p className="text-xs text-white/40 text-center">FeedPilot v0.1</p>
      </div>
    </aside>
  )
}
