"use client";

import { FileUploadZone } from "@/components/upload/FileUploadZone";
import { JobStatusList }  from "@/components/upload/JobStatusList";

export default function UploadPage() {
  return (
    <div className="p-8 space-y-8 animate-fade-in max-w-4xl">
      <div>
        <h1 className="text-2xl font-display font-semibold text-slate-100">
          Data Ingestion
        </h1>
        <p className="text-slate-400 mt-1 text-sm">
          Upload CSV datasets or clinical PDF documents for AI analysis.
        </p>
      </div>
      <FileUploadZone />
      <JobStatusList />
    </div>
  );
}
