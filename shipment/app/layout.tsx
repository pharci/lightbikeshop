import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Склад заказов — WB и Ozon",
  description: "Заказы, резервы, остатки и этикетки Wildberries и Ozon в одном окне.",
  icons: {
    icon: "/shipment/favicon.svg",
    shortcut: "/shipment/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <head>
        <meta httpEquiv="Cache-Control" content="no-store, no-cache, must-revalidate" />
        <meta httpEquiv="Pragma" content="no-cache" />
        <meta httpEquiv="Expires" content="0" />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
