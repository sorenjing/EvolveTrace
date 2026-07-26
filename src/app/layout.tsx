import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ErrorBoundary } from "@/app/components/ErrorBoundary";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EvolveLab - Coding Agent 可观测性与安全边界研究项目",
  description: "研究 Coding Agent 的可观测性、工具扩展与安全边界。",
};

// 内联脚本：在 HTML 阶段就根据 localStorage 设置主题 class，避免暗色闪烁（FOUC）
const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('evolvelab_theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var useDark = t ? t === 'dark' : prefersDark;
    if (useDark) document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
