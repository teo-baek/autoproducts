import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ezmerce — Wholesale Management",
  description: "폐쇄형 B2B 도매 카탈로그 · 주문 솔루션",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <head>
        {/* 본문/헤딩 = Pretendard, 로고타입 = Playfair Display italic (DESIGN-SYSTEM §2) */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/static/pretendard.min.css"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,500;1,600;1,700&display=swap"
        />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
