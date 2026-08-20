import { create } from "zustand";
import type { IngestionJob } from "@/types";

interface JobState {
  jobs:      IngestionJob[];
  addJob:    (job: IngestionJob) => void;
  updateJob: (job: IngestionJob) => void;
  clearJobs: () => void;
}

export const useJobStore = create<JobState>((set) => ({
  jobs: [],

  addJob: (job) =>
    set((s) => ({ jobs: [job, ...s.jobs] })),

  updateJob: (updated) =>
    set((s) => ({
      jobs: s.jobs.map((j) => (j.job_id === updated.job_id ? updated : j)),
    })),

  clearJobs: () => set({ jobs: [] }),
}));
