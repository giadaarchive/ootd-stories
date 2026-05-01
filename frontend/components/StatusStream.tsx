"use client"

import type { StreamEvent } from "@/app/page"

interface Props {
  events: StreamEvent[]
  loading: boolean
}

export default function StatusStream({ events, loading }: Props) {
  const visible = events.filter(
    (e) => e.type === "brand" || e.type === "codes_found" || e.type === "error"
  )

  if (!visible.length && !loading) return null

  return (
    <div className="space-y-1.5">
      {visible.map((event, i) => {
        if (event.type === "brand") {
          const icon =
            event.status === "cached" ? "·" :
            event.status === "fetching" ? "↓" : "✓"
          const colour =
            event.status === "cached" ? "text-stone-300" :
            event.status === "fetching" ? "text-amber-500" : "text-emerald-500"
          return (
            <div key={i} className="flex items-center gap-2.5 text-xs">
              <span className={`font-mono w-3 text-center ${colour}`}>{icon}</span>
              <span className="text-stone-500">
                {event.brand}
                <span className="text-stone-300 mx-1">·</span>
                {event.season}
              </span>
              {event.status === "done" && event.codes_added !== undefined && (
                <span className="text-stone-300">{event.codes_added} codes</span>
              )}
              {event.status === "cached" && (
                <span className="text-stone-300">cached</span>
              )}
              {event.status === "fetching" && (
                <span className="text-amber-400 animate-pulse">fetching…</span>
              )}
            </div>
          )
        }

        if (event.type === "codes_found") {
          return (
            <div key={i} className="flex items-center gap-2.5 text-xs pt-1 mt-1 border-t border-stone-100">
              <span className="font-mono w-3 text-center text-stone-300">—</span>
              <span className="text-stone-400">
                {event.count} instances across {event.brands.length} houses
              </span>
            </div>
          )
        }

        if (event.type === "error") {
          return (
            <div key={i} className="text-xs text-red-400 flex gap-2">
              <span>!</span>
              <span>{event.message}</span>
            </div>
          )
        }

        return null
      })}

      {loading && !visible.some((e) => e.type === "brand") && (
        <div className="flex items-center gap-2.5 text-xs text-stone-300 animate-pulse">
          <span className="font-mono w-3 text-center">·</span>
          <span>Checking runway coverage…</span>
        </div>
      )}
    </div>
  )
}
