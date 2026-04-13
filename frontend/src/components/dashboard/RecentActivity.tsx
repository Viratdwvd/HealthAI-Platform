"use client";

import { CheckCircle2, FileUp, AlertCircle, Zap } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";

const EVENTS = [
  { type: "query",    msg: "Query: 'What is the 30-day readmission rate?'", ts: new Date(Date.now() - 2 * 60000) },
  { type: "ingest",   msg: "Uploaded: patient_outcomes_Q2_2024.csv (4,312 rows)", ts: new Date(Date.now() - 18 * 60000) },
  { type: "forecast", msg: "Forecast completed: ICU bed occupancy (30-day)", ts: new Date(Date.now() - 45 * 60000) },
  { type: "alert",    msg: "Retrieval confidence below threshold (0.38)", ts: new Date(Date.now() - 2 * 3600000) },
  { type: "query",    msg: "Query: 'Summarise hypertension medication compliance'", ts: new Date(Date.now() - 3 * 3600000) },
  { type: "ingest",   msg: "Uploaded: clinical_notes_batch_17.pdf (89 pages)", ts: new Date(Date.now() - 5 * 3600000) },
];

const TYPE_META: Record<string, { icon: React.ElementType; cls: string }> = {
  query:    { icon: Zap,          cls: "bg-brand-500/10 text-brand-400"   },
  ingest:   { icon: FileUp,       cls: "bg-emerald-500/10 text-emerald-400" },
  forecast: { icon: CheckCircle2, cls: "bg-violet-500/10 text-violet-400"  },
  alert:    { icon: AlertCircle,  cls: "bg-rose-500/10 text-rose-400"     },
};

export function RecentActivity() {
  return (
    <div className="card p-5">
      <h2 className="text-sm font-semibold text-slate-300 mb-4">Recent Activity</h2>
      <div className="space-y-1">
        {EVENTS.map((ev, i) => {
          const meta = TYPE_META[ev.type];
          const Icon = meta.icon;
          return (
            <div
              key={i}
              className="flex items-start gap-3 px-2 py-2.5 rounded-lg hover:bg-surface-800 transition-colors"
            >
              <div className={clsx("mt-0.5 w-6 h-6 rounded-md flex items-center justify-center shrink-0", meta.cls)}>
                <Icon size={13} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-300 truncate">{ev.msg}</p>
              </div>
              <span className="text-xs text-slate-500 shrink-0">
                {formatDistanceToNow(ev.ts, { addSuffix: true })}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
