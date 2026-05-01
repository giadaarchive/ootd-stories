"use client"

import { useState, useRef, useEffect } from "react"
import SearchBox from "@/components/SearchBox"
import StatusStream from "@/components/StatusStream"
import AnswerPanel from "@/components/AnswerPanel"

export type StreamEvent =
  | { type: "status"; message: string }
  | { type: "brand"; brand: string; season: string; status: "cached" | "fetching" | "done"; codes_added?: number }
  | { type: "codes_found"; count: number; brands: string[] }
  | { type: "answer"; content: string; season: string; gender: string; categories: string[] }
  | { type: "error"; message: string }
  | { type: "log"; message: string }
  | { type: "done"; exit_code: number }

const EXAMPLE_QUESTIONS = [
  "What colours will I see in SS2026?",
  "What silhouette is dominant this season?",
  "What materials are trending for AW2026?",
  "Which houses are using prints this spring?",
  "What is the mood at Hermès this season?",
]

export default function Home() {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [answer, setAnswer] = useState<string>("")
  const [loading, setLoading] = useState(false)
  const [asked, setAsked] = useState<string>("")
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [events, answer])

  async function handleQuery(question: string) {
    if (!question.trim() || loading) return

    // Reset
    if (abortRef.current) abortRef.current.abort()
    abortRef.current = new AbortController()
    setEvents([])
    setAnswer("")
    setAsked(question)
    setLoading(true)

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: abortRef.current.signal,
      })

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buf = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })
        const lines = buf.split("\n")
        buf = lines.pop() ?? ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const event: StreamEvent = JSON.parse(raw)
            if (event.type === "answer") {
              setAnswer(event.content)
            } else if (event.type !== "done" && event.type !== "log") {
              setEvents((prev) => [...prev, event])
            }
          } catch {
            // non-JSON line, ignore
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setEvents((prev) => [...prev, { type: "error", message: String(err) }])
      }
    } finally {
      setLoading(false)
    }
  }

  const hasResult = answer || events.some((e) => e.type === "error")
  const idle = !loading && !hasResult

  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 flex items-center justify-between border-b border-stone-100">
        <span className="text-xs font-medium tracking-[0.2em] uppercase text-stone-400">
          Andromeda
        </span>
        <span className="text-xs text-stone-300">Fashion Intelligence</span>
      </header>

      {/* Hero / Search area */}
      <section
        className={`flex flex-col items-center transition-all duration-500 ${
          idle ? "justify-center flex-1 pb-24" : "pt-12 pb-8"
        }`}
      >
        {idle && (
          <h1
            className="font-serif text-4xl md:text-5xl text-stone-800 mb-10 text-center leading-tight"
            style={{ fontFamily: "'DM Serif Display', Georgia, serif" }}
          >
            What do you want to know
            <br />
            <span className="italic text-stone-400">about fashion?</span>
          </h1>
        )}

        <div className="w-full max-w-2xl px-4">
          <SearchBox onSubmit={handleQuery} loading={loading} />
        </div>

        {/* Example questions — only shown idle */}
        {idle && (
          <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-2xl px-4">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleQuery(q)}
                className="text-xs text-stone-500 border border-stone-200 rounded-full px-4 py-1.5 hover:border-stone-400 hover:text-stone-700 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Results area */}
      {!idle && (
        <section className="flex-1 max-w-2xl mx-auto w-full px-4 pb-16">
          {asked && (
            <p className="text-sm text-stone-400 mb-6">
              <span className="font-medium text-stone-600">&ldquo;{asked}&rdquo;</span>
            </p>
          )}

          <StatusStream events={events} loading={loading} />

          {answer && (
            <div className="mt-8">
              <AnswerPanel answer={answer} />
            </div>
          )}

          <div ref={bottomRef} />
        </section>
      )}
    </main>
  )
}
