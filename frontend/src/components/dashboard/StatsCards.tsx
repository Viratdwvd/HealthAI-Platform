"use client";

import { FileText, MessageSquare, TrendingUp, Database } from "lucide-react";
import clsx from "clsx";

const STATS = [
  { label: "Documents Indexed",   value: "2,841",  delta: "+124 this week",  icon: Database,       color: "blue"   },
  { label: "Queries Answered",    value: "10,392", delta: "+890 this week",  icon: MessageSquare,  color: "green"  },
  { label: "Forecasts Run",       value: "347",    delta: "+42 this week",   icon: TrendingUp,     color: "purple" },
  { label: "Reports Generated",   value: "89",     delta: "+12 this week",   icon: FileText,       color: "amber"  },
];

const COLOR_MAP: Record<string, string> = {
  blue:   "bg-brand-500/10 text-brand-400",
  green:  "bg-emerald-500/10 text-emerald-400",
  purple: "bg-violet-500/10 text-violet-400",
  amber:  "bg-amber-500/10 text-amber-400",
};

export function StatsCards() {
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
      {STATS.map(({ label, value, delta, icon: Icon, color }) => (
        <div key={label} className="card p-5 animate-slide-up">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium">{label}</p>
              <p className="text-2xl font-semibold text-slate-100 mt-1">{value}</p>
              <p className="text-xs text-slate-500 mt-1">{delta}</p>
            </div>
            <div className={clsx("w-9 h-9 rounded-lg flex items-center justify-center", COLOR_MAP[color])}>
              <Icon size={16} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
