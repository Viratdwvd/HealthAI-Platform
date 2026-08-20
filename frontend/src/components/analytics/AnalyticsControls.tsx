"use client";

import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { AnalyticsResult } from "@/types";

interface Props { onResult: (r: AnalyticsResult) => void }

const DEMO_CSV = `ds,y
2023-01-01,120
2023-02-01,135
2023-03-01,128
2023-04-01,145
2023-05-01,162
2023-06-01,158
2023-07-01,170
2023-08-01,155
2023-09-01,182
2023-10-01,190
2023-11-01,178
2023-12-01,200`;

function parseCsvRows(csv: string) {
  const [header, ...rows] = csv.trim().split("\n");
  const keys = header.split(",");
  return rows.map((r) => {
    const vals = r.split(",");
    return Object.fromEntries(keys.map((k, i) => [k, vals[i]]));
  });
}

export function AnalyticsControls({ onResult }: Props) {
  const [operation, setOperation] = useState<"forecast" | "stats">("forecast");
  const [csvText,   setCsvText]   = useState(DEMO_CSV);
  const [horizon,   setHorizon]   = useState(30);
  const [loading,   setLoading]   = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const rows = parseCsvRows(csvText);
      const resp = await api.analytics({
        operation,
        dataset_id: "inline",
        params: {
          data:    rows,
          horizon: Number(horizon),
        },
      });

      const result: AnalyticsResult = {
        operation: resp.operation,
        forecast:  resp.operation === "forecast" ? resp.result : undefined,
        stats:     resp.operation !== "forecast" ? resp.result : undefined,
      };
      onResult(result);
    } catch (err: any) {
      toast.error(err?.message ?? "Analytics failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-300">Configure Analysis</h2>

      {/* Operation */}
      <div className="flex gap-2">
        {(["forecast", "stats"] as const).map((op) => (
          <button
            key={op}
            onClick={() => setOperation(op)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              operation === op
                ? "bg-brand-600 text-white"
                : "bg-surface-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            {op === "forecast" ? "Forecast" : "Statistics"}
          </button>
        ))}
      </div>

      {/* CSV Input */}
      <div>
        <label className="block text-xs text-slate-500 mb-1.5">
          Data (CSV with header row)
        </label>
        <textarea
          rows={8}
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
          className="input font-mono text-xs"
          spellCheck={false}
        />
      </div>

      {/* Horizon (forecast only) */}
      {operation === "forecast" && (
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">
            Forecast horizon (days): <span className="text-slate-300">{horizon}</span>
          </label>
          <input
            type="range"
            min={7} max={365} step={7}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="w-full accent-brand-500"
          />
        </div>
      )}

      {/* Run */}
      <button onClick={run} disabled={loading} className="btn-primary flex items-center gap-2">
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
        {loading ? "Running…" : "Run Analysis"}
      </button>
    </div>
  );
}
