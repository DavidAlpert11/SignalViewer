/* W14 / W15 / W17 / W18: the calls of the Common parameters panel (backend app/routes/sweeps_common.py,
   sweeps_farm.py). Types: studyTypes.ts (the W0 contract). */
import { call } from "../api";
import type { CommonResult, DemoProgress, LoopProgress, LauncherStatusResult, LauncherSubmitResult, NextRunsResult, Study, StudyReq } from "./studyTypes";

export const studyApi = {
  open: (study_path: string) => call<{ path: string; study: Study }>("/api/sweeps/study/open", { study_path }),
  save: (path: string, study: Study) => call<{ path: string }>("/api/sweeps/study/save", { path, study }),
  mapping: (paths: Record<string, string[]>) =>
    call<{ columns: Record<string, string[]>; roles: Record<string, Record<string, string>>; mapping: { table: string; column: string; name: string; score: number }[] }>("/api/sweeps/mapping", { paths }),
  common: (req: StudyReq) => call<CommonResult>("/api/sweeps/common", req),
  runs: (req: StudyReq, table: string, rows: number[]) =>
    call<{ table: string; columns: string[]; rows: (number | string | null)[][] }>("/api/sweeps/common/runs", { ...req, table, rows }),
  exportCsv: (req: StudyReq, path: string) => call<{ path: string; rows: number }>("/api/sweeps/common/export", { ...req, path }),
  nextRuns: (req: StudyReq) => call<NextRunsResult>("/api/sweeps/next-runs", req),
  submit: (study_path: string, confirmed: boolean) => call<LauncherSubmitResult>("/api/sweeps/launcher/submit", { study_path, confirmed }),
  status: (study_path: string) => call<LauncherStatusResult>(`/api/sweeps/launcher/status?study_path=${encodeURIComponent(study_path)}`),
  demoStep: (study_path: string, action: "next" | "run" | "reset" | "stop") => call<DemoProgress>("/api/sweeps/demo/step", { study_path, action }),
  loop: (study_path: string, action: "next" | "run" | "stop" | "reset") => call<LoopProgress>("/api/sweeps/loop", { study_path, action }),
  loopProgress: (study_path: string) => call<LoopProgress>(`/api/sweeps/loop/progress?study_path=${encodeURIComponent(study_path)}`),
  copyDemo: (study_path: string, folder: string) => call<{ path: string }>("/api/sweeps/demo/copy", { study_path, folder }),
  demoProgress: (study_path: string) => call<DemoProgress>(`/api/sweeps/demo/progress?study_path=${encodeURIComponent(study_path)}`),
};
