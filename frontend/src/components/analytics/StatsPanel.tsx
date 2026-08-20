"use client";

interface Props { stats: Record<string, any> }

export function StatsPanel({ stats }: Props) {
  const numeric = stats.numeric_stats ?? {};
  const cols    = Object.keys(numeric);

  return (
    <div className="card p-5 space-y-4">
      <h3 className="text-sm font-semibold text-slate-200">Descriptive Statistics</h3>

      {stats.shape && (
        <div className="flex gap-3">
          <Chip label="Rows"    value={stats.shape.rows} />
          <Chip label="Columns" value={stats.shape.columns} />
        </div>
      )}

      {cols.map((col) => {
        const s = numeric[col];
        return (
          <div key={col} className="space-y-1.5">
            <p className="text-xs font-medium text-slate-400">{col}</p>
            <div className="grid grid-cols-2 gap-1">
              {["mean", "std", "min", "max"].map((k) =>
                s[k] != null ? (
                  <div key={k} className="flex justify-between px-2 py-1 rounded bg-surface-800">
                    <span className="text-[10px] text-slate-500 uppercase">{k}</span>
                    <span className="text-[11px] text-slate-300 font-mono">
                      {Number(s[k]).toFixed(2)}
                    </span>
                  </div>
                ) : null
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Chip({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1 bg-surface-800 rounded-lg px-3 py-2">
      <p className="text-[10px] text-slate-500 uppercase">{label}</p>
      <p className="text-lg font-semibold text-slate-200 leading-none mt-0.5">{value}</p>
    </div>
  );
}
