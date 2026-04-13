"use client";

import { useCallback, useState } from "react";
import { useDropzone }           from "react-dropzone";
import { UploadCloud, File, X, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import clsx                      from "clsx";
import toast                     from "react-hot-toast";
import { api }                   from "@/lib/api";
import { useJobStore }           from "@/hooks/useJobStore";

const ACCEPTED = {
  "text/csv":                        [".csv"],
  "application/pdf":                 [".pdf"],
  "application/json":                [".json"],
};

interface UploadFile {
  id:       string;
  file:     File;
  status:   "pending" | "uploading" | "done" | "error";
  error?:   string;
  job_id?:  string;
}

export function FileUploadZone() {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const { addJob }        = useJobStore();

  const updateFile = (id: string, patch: Partial<UploadFile>) =>
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));

  const upload = useCallback(
    async (uf: UploadFile) => {
      updateFile(uf.id, { status: "uploading" });
      try {
        const b64 = await toBase64(uf.file);
        const ext  = uf.file.name.split(".").pop()!.toLowerCase() as "csv" | "pdf" | "json";

        const job = await api.ingest({
          file_name:   uf.file.name,
          file_type:   ext,
          content_b64: b64,
        });

        addJob(job);
        updateFile(uf.id, { status: "done", job_id: job.job_id });
        toast.success(`${uf.file.name} queued for processing`);
      } catch (err: any) {
        updateFile(uf.id, { status: "error", error: err?.message ?? "Upload failed" });
        toast.error(`Failed to upload ${uf.file.name}`);
      }
    },
    [addJob]
  );

  const onDrop = useCallback(
    (accepted: File[]) => {
      const newFiles: UploadFile[] = accepted.map((file) => ({
        id:     Math.random().toString(36).slice(2),
        file,
        status: "pending",
      }));
      setFiles((prev) => [...prev, ...newFiles]);
      newFiles.forEach(upload);
    },
    [upload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept:   ACCEPTED,
    maxSize:  50 * 1024 * 1024,    // 50 MB
    multiple: true,
  });

  const remove = (id: string) =>
    setFiles((prev) => prev.filter((f) => f.id !== id));

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={clsx(
          "border-2 border-dashed rounded-xl px-8 py-12 flex flex-col items-center gap-3 cursor-pointer transition-colors duration-150",
          isDragActive
            ? "border-brand-500 bg-brand-500/5"
            : "border-surface-700 hover:border-brand-500/50 hover:bg-surface-800/50"
        )}
      >
        <input {...getInputProps()} />
        <UploadCloud
          size={36}
          className={clsx(
            "transition-colors",
            isDragActive ? "text-brand-400" : "text-slate-600"
          )}
        />
        <div className="text-center">
          <p className="text-sm font-medium text-slate-300">
            {isDragActive ? "Drop files here" : "Drag & drop files, or click to browse"}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            CSV, PDF, or JSON · up to 50 MB each
          </p>
        </div>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="card divide-y divide-surface-800">
          {files.map((uf) => (
            <FileRow key={uf.id} uf={uf} onRemove={() => remove(uf.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function FileRow({ uf, onRemove }: { uf: UploadFile; onRemove: () => void }) {
  const sizeStr = (uf.file.size / 1024).toFixed(0) + " KB";

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <File size={16} className="text-slate-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-300 truncate">{uf.file.name}</p>
        <p className="text-xs text-slate-500">{sizeStr}</p>
      </div>
      <StatusIcon status={uf.status} />
      {(uf.status === "pending" || uf.status === "error") && (
        <button onClick={onRemove} className="text-slate-600 hover:text-slate-400 transition-colors">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: UploadFile["status"] }) {
  switch (status) {
    case "uploading": return <Loader2  size={16} className="text-brand-400 animate-spin" />;
    case "done":      return <CheckCircle size={16} className="text-emerald-400" />;
    case "error":     return <AlertCircle size={16} className="text-rose-400" />;
    default:          return <span className="w-4 h-4 rounded-full border border-slate-600" />;
  }
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
