"use client";

import { ForecastChart }    from "@/components/analytics/ForecastChart";
import { StatsPanel }       from "@/components/analytics/StatsPanel";
import { AnalyticsControls } from "@/components/analytics/AnalyticsControls";
import { useState }         from "react";
import type { AnalyticsResult } from "@/types";

export default function AnalyticsPage() {
  const [result, setResult] = useState<AnalyticsResult | null>(null);

  return (
    <div className="p-8 space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-semibold text-slate-100">Analytics</h1>
        <p className="text-slate-400 mt-1 text-sm">
          Time-series forecasting and statistical summaries of your datasets.
        </p>
      </div>

      <AnalyticsControls onResult={setResult} />

      {result && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            {result.operation === "forecast" && result.forecast && (
              <ForecastChart forecast={result.forecast} />
            )}
          </div>
          <div>
            {result.stats && <StatsPanel stats={result.stats} />}
          </div>
        </div>
      )}
    </div>
  );
}
