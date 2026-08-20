"use client";

import { useEffect }     from "react";
import { useQuery }      from "@tanstack/react-query";
import { CheckCircle2, Clock, Loader2, XCircle, FileText } from "lucide-react";
import clsx              from "clsx";
import { api }           from "@/lib/api";
import { useJobStore }   from "@/hooks/useJobStore";
import type { IngestionJob } from "@/types";

export function JobStatusList() {
  const { jobs, updateJob } = useJobStore();

  // Poll in-progress jobs every 3s
  const runningIds = jobs.filter((j) => ["pending", "running"].includes(j.status)).map((j) => j.job_id);

  useEffect(() => {
    if (runningIds.length === 0) return;

    const interval = setInterval(async () => {
      for (const id of runningIds) {
        try {
          const updated = await api.jobStatus(id);
          updateJob(updated);
        } catch {}
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [runningIds.join(",")]); // eslint-disable-line

  if (jobs.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-400 mb-3">Ingestion Jobs</h2>
      <div className="card divide-y divide-surface-800">
        {jobs.map((job) => (
          <JobRow key={job.job_id} job={job} />
        ))}
      </div>
    </div>
  );
}

function JobRow({ job }: { job: IngestionJob }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <FileText size={15} className="text-slate-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-300 truncate">{job.file_name}</p>
        <p className="text-xs text-slate-500">
          {job.chunks ? `${job.chunks} chunks` : job.file_type}
          {job.error && (
            <span className="text-rose-400 ml-2">{job.error}</span>
          )}
        </p>
      </div>
      <StatusChip status={job.status} />
    </div>
  );
}

const STATUS_META: Record<string, { icon: React.ElementType; cls: string; label: string }> = {
  pending:  { icon: Clock,        cls: "badge bg-slate-700/50 text-slate-400",    label: "Pending"    },
  running:  { icon: Loader2,      cls: "badge badge-blue",                         label: "Processing" },
  done:     { icon: CheckCircle2, cls: "badge badge-green",                        label: "Indexed"    },
  failed:   { icon: XCircle,      cls: "badge badge-red",                          label: "Failed"     },
};

function StatusChip({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  const Icon = meta.icon;
  return (
    <span className={meta.cls}>
      <Icon size={10} className={status === "running" ? "animate-spin" : ""} />
      {meta.label}
    </span>
  );
}
