import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Guia Melhores Escolhas | Reviews Inteligentes",
  description: "Análises detalhadas e imparciais dos melhores produtos do mercado.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-background text-foreground antialiased`}>
        <nav className="border-b border-gray-200 bg-white/80 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
            <a href="/" className="font-bold text-xl tracking-tight text-blue-600">
              Guia<span className="text-gray-900">MelhoresEscolhas</span>
            </a>
            <div className="flex gap-6 text-sm font-medium text-gray-600">
              <a href="/" className="hover:text-blue-600 transition-colors">Site (Home)</a>
              <a href="/admin/dashboard" className="hover:text-blue-600 transition-colors">Dashboard (Admin)</a>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html >
  );
}
