"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { ForecastResult } from "@/types";

interface Props { forecast: ForecastResult }

export function ForecastChart({ forecast }: Props) {
  const data = forecast.dates.map((d, i) => ({
    date:     d,
    value:    forecast.values[i],
    lower:    forecast.lower_ci[i],
    upper:    forecast.upper_ci[i],
  }));

  const formatDate = (d: string) => {
    try { return format(parseISO(d), "MMM d"); }
    catch { return d; }
  };

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Forecast</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Model: <span className="text-brand-400">{forecast.model_used}</span>
            &nbsp;·&nbsp;{forecast.dates.length}-day horizon
          </p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="ci" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#27a6f6" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#27a6f6" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={{ stroke: "#1e293b" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
            labelFormatter={formatDate}
            formatter={(v: number) => [v.toFixed(2)]}
          />
          {/* CI band */}
          <Area
            dataKey="upper"
            stroke="transparent"
            fill="url(#ci)"
            name="Upper CI"
          />
          <Area
            dataKey="lower"
            stroke="transparent"
            fill="#0f172a"       // cancel out the band below lower
            name="Lower CI"
          />
          {/* Forecast line */}
          <Area
            dataKey="value"
            stroke="#27a6f6"
            strokeWidth={2}
            fill="transparent"
            dot={false}
            activeDot={{ r: 4, fill: "#27a6f6" }}
            name="Forecast"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
