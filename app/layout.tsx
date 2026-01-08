import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FinOps CUR Scenario Dashboard',
  description: 'Upload AWS CUR CSV to analyze cost scenarios',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

