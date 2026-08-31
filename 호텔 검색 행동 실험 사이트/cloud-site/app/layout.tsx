import type { Metadata } from "next";
import "./globals.css";
import "./rooms.css";

export const metadata: Metadata = {
  title: "StayTrace · 호텔 검색 행동 실험실",
  description: "일본 가상 호텔 검색과 사용자 행동 로그 분석",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
