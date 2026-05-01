"use client"

interface Props {
  answer: string
}

function formatAnswer(text: string): string {
  // Bold **text** → <strong>
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Numbered lists
    .replace(/^(\d+)\.\s+/gm, "<br/><strong>$1.</strong> ")
    // Paragraph breaks
    .split(/\n\n+/)
    .map((p) => `<p>${p.trim()}</p>`)
    .join("")
}

export default function AnswerPanel({ answer }: Props) {
  return (
    <div className="border-l-2 border-stone-800 pl-6">
      <div
        className="answer-prose text-sm text-stone-700 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: formatAnswer(answer) }}
      />
      <p className="mt-4 text-xs text-stone-300">
        Sourced from runway collections via tag-walk · Andromeda
      </p>
    </div>
  )
}
