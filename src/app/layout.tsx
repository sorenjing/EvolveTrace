import type { Metadata } from "next";
import "./globals.css";
import { ErrorBoundary } from "@/app/components/ErrorBoundary";

export const metadata: Metadata = {
  title: "EvolveTrace — Coding Agent Review Workbench",
  description: "Review and observe local coding agent execution evidence.",
};

const themeInitScript = `
(function() {
  try {
    var theme = localStorage.getItem('evolvelab_theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (theme === 'dark' || (!theme && prefersDark)) document.documentElement.classList.add('dark');
  } catch (error) {}
})();
`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning className="h-full antialiased">
      <head><script dangerouslySetInnerHTML={{ __html: themeInitScript }} /></head>
      <body className="min-h-full"><ErrorBoundary>{children}</ErrorBoundary></body>
    </html>
  );
}
