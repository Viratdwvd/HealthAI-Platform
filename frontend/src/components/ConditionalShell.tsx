"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar";

export function ConditionalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  if (isLogin) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}