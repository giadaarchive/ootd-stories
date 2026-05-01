"use client"

import { useState, useRef, useEffect } from "react"

interface Props {
  onSubmit: (q: string) => void
  loading: boolean
}

export default function SearchBox({ onSubmit, loading }: Props) {
  const [value, setValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && value.trim()) {
      onSubmit(value.trim())
    }
  }

  return (
    <div className="relative flex items-center w-full bg-white border border-stone-200 rounded-2xl shadow-sm hover:shadow-md focus-within:shadow-md focus-within:border-stone-400 transition-all">
      {/* Search icon */}
      <svg
        className="ml-5 shrink-0 text-stone-300"
        width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      >
        <circle cx="11" cy="11" r="8" />
        <path d="M21 21l-4.35-4.35" />
      </svg>

      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        disabled={loading}
        placeholder="Ask about colours, materials, silhouettes, trends…"
        className="flex-1 bg-transparent px-4 py-4 text-sm text-stone-700 placeholder-stone-300 outline-none disabled:opacity-50"
      />

      {/* Loading spinner or submit button */}
      <div className="mr-3">
        {loading ? (
          <div className="w-5 h-5 border-2 border-stone-200 border-t-stone-500 rounded-full animate-spin" />
        ) : (
          <button
            onClick={() => value.trim() && onSubmit(value.trim())}
            disabled={!value.trim()}
            className="flex items-center justify-center w-8 h-8 rounded-xl bg-stone-800 text-white disabled:opacity-20 hover:bg-stone-700 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
