import type { Metadata } from "next";
import "./globals.css";
import Providers from "../components/Providers";
import { THEME_KEY } from "../lib/themeKey";

// Runs before first paint so the saved theme never flashes the wrong colors.
const themeScript = `try{var c=localStorage.getItem("${THEME_KEY}");if(c==="dark"||((c===null||c==="system")&&matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")}catch(e){}`;

export const metadata: Metadata = {
  title: "CULTURESYNC - Cultural intelligence for teams",
  description: "Discover shared cultural interests across your team and turn overlap into real collaboration.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
