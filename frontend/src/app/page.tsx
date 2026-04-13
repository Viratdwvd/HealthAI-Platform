"use client";

import { StatsCards }   from "@/components/dashboard/StatsCards";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { QueryBar }     from "@/components/chat/QueryBar";
import { useRouter }    from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();

  return (
    <div className="p-8 space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-semibold text-slate-100">
          Healthcare Intelligence
        </h1>
        <p className="text-slate-400 mt-1 text-sm">
          AI-powered insights from your clinical & operational data
        </p>
      </div>

      {/* Quick query */}
      <div className="card p-4">
        <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider font-medium">
          Quick Query
        </p>
        <QueryBar
          placeholder="Ask anything about your data…"
          onSubmit={(q) => router.push(`/chat?q=${encodeURIComponent(q)}`)}
        />
      </div>

      {/* Stats */}
      <StatsCards />

      {/* Activity */}
      <RecentActivity />
    </div>
  );
}
