import { spawn } from "child_process"
import path from "path"

export const runtime = "nodejs"
export const maxDuration = 120

export async function POST(request: Request) {
  const { question } = await request.json()
  if (!question?.trim()) {
    return new Response(JSON.stringify({ error: "No question provided" }), { status: 400 })
  }

  const repoRoot = path.resolve(process.cwd(), "..")
  const scriptPath = path.join(repoRoot, "house_codes", "query_engine.py")

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    start(controller) {
      const proc = spawn("python3", [scriptPath, "--stream", question], {
        cwd: repoRoot,
        env: { ...process.env },
      })

      let buffer = ""

      proc.stdout.on("data", (chunk: Buffer) => {
        buffer += chunk.toString()
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) continue
          // Forward each JSON line as an SSE event
          controller.enqueue(encoder.encode(`data: ${trimmed}\n\n`))
        }
      })

      proc.stderr.on("data", (chunk: Buffer) => {
        // Forward stderr as a status event so the frontend can show it
        const msg = chunk.toString().trim()
        if (msg) {
          const event = JSON.stringify({ type: "log", message: msg })
          controller.enqueue(encoder.encode(`data: ${event}\n\n`))
        }
      })

      proc.on("close", (code) => {
        const done = JSON.stringify({ type: "done", exit_code: code })
        controller.enqueue(encoder.encode(`data: ${done}\n\n`))
        controller.close()
      })

      proc.on("error", (err) => {
        const errEvent = JSON.stringify({ type: "error", message: err.message })
        controller.enqueue(encoder.encode(`data: ${errEvent}\n\n`))
        controller.close()
      })
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  })
}
