import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Andromeda — Fashion Intelligence",
  description: "Ask anything about runway trends, colours, materials, and silhouettes across global collections.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#fafaf8]">{children}</body>
    </html>
  )
}
