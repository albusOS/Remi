import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "REMI — Property Intelligence",
  description: "AI-powered property management analytics and operations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Anti-FOUC: set data-theme before first paint so CSS vars resolve correctly */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('remi-theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);return;}var sys=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';document.documentElement.setAttribute('data-theme',sys);}catch(e){}})();`,
          }}
        />
      </head>
      <body className="h-screen overflow-hidden bg-surface text-fg antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
