import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Green Permit Intake",
  description: "白ナンバーから緑ナンバー切替申請の入力支援アプリ",
  applicationName: "Green Permit Intake",
  manifest: "/manifest.webmanifest"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
