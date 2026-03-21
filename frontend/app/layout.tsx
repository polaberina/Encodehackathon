import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { SimulationProvider } from '@/lib/simulation-context'
import { SimulationHeader } from '@/components/simulation/simulation-header'
import './globals.css'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: 'R.E.A.C.T - Energy Grid Simulation',
  description: 'Multi-Agent Reinforcement Learning Environment for Power Grid Management',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased bg-background text-foreground">
        <SimulationProvider>
          <div className="min-h-screen flex flex-col">
            <SimulationHeader />
            <main className="flex-1">
              {children}
            </main>
          </div>
        </SimulationProvider>
        <Analytics />
      </body>
    </html>
  )
}
