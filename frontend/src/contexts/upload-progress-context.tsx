"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type UploadPhase = "idle" | "uploading" | "processing" | "success" | "error";

export type UploadResult = {
  id: number;
  original_filename: string;
  parse_status: string;
  parse_error: string | null;
  upload_date: string;
};

type JobState = {
  phase: UploadPhase;
  filename: string;
  progress: number;
  message: string | null;
};

const initialJob: JobState = {
  phase: "idle",
  filename: "",
  progress: 0,
  message: null,
};

type Ctx = {
  job: JobState;
  startUpload: (file: File, parserOptions?: string) => Promise<UploadResult>;
  dismissBanner: () => void;
};

const UploadProgressContext = createContext<Ctx | null>(null);

function xhrUpload(formData: FormData, token: string | null): {
  promise: Promise<UploadResult>;
  onUploadProgress: (cb: (pct: number, indeterminate: boolean) => void) => void;
  onUploadDone: (cb: () => void) => void;
} {
  let progressCb: ((pct: number, indeterminate: boolean) => void) | null = null;
  let uploadDoneCb: (() => void) | null = null;

  const promise = new Promise<UploadResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/v1/uploads`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable && ev.total > 0) {
        progressCb?.(Math.min(100, Math.round((ev.loaded / ev.total) * 100)), false);
      } else {
        progressCb?.(0, true);
      }
    };

    xhr.upload.onload = () => {
      uploadDoneCb?.();
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResult);
        } catch {
          reject(new Error("响应不是合法 JSON"));
        }
      } else {
        reject(new Error(xhr.responseText || xhr.statusText || "上传失败"));
      }
    };
    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.onabort = () => reject(new Error("已取消"));
    xhr.send(formData);
  });

  return {
    promise,
    onUploadProgress: (cb) => {
      progressCb = cb;
    },
    onUploadDone: (cb) => {
      uploadDoneCb = cb;
    },
  };
}

export function UploadProgressProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [job, setJob] = useState<JobState>(initialJob);
  const jobRef = useRef(job);
  jobRef.current = job;

  useEffect(() => {
    const p = job.phase;
    if (p !== "uploading" && p !== "processing") return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [job.phase]);

  const dismissBanner = useCallback(() => {
    setJob(initialJob);
  }, []);

  const startUpload = useCallback(
    async (file: File, parserOptions?: string) => {
      const cur = jobRef.current;
      if (cur.phase === "uploading" || cur.phase === "processing") {
        throw new Error("已有上传或处理任务进行中，请等待结束后再试");
      }

      const formData = new FormData();
      formData.append("file", file);
      if (parserOptions) formData.append("parser_options", parserOptions);

      setJob({
        phase: "uploading",
        filename: file.name,
        progress: 0,
        message: null,
      });

      const { promise, onUploadProgress, onUploadDone } = xhrUpload(formData, getToken());

      onUploadProgress((pct, indeterminate) => {
        setJob((j) => {
          if (j.phase !== "uploading") return j;
          return {
            ...j,
            progress: indeterminate ? Math.max(j.progress, 1) : pct,
            message: indeterminate ? "正在上传（无法计算进度）…" : null,
          };
        });
      });

      onUploadDone(() => {
        setJob((j) => ({
          ...j,
          phase: "processing",
          progress: 100,
          message: "文件已送达服务器，正在解析、去重与写入数据库，大文件可能需数分钟…",
        }));
      });

      try {
        const result = await promise;
        await qc.invalidateQueries({ queryKey: ["uploads"] });
        await qc.invalidateQueries({ queryKey: ["days"] });
        await qc.invalidateQueries({ queryKey: ["dashboard"] });
        setJob({
          phase: "success",
          filename: file.name,
          progress: 100,
          message: `「${file.name}」处理完成（状态：${result.parse_status}）`,
        });
        window.setTimeout(() => {
          if (jobRef.current.phase === "success") setJob(initialJob);
        }, 8000);
        return result;
      } catch (e) {
        const err = (e as Error).message || "上传失败";
        setJob({
          phase: "error",
          filename: file.name,
          progress: 0,
          message: err,
        });
        throw e;
      }
    },
    [qc]
  );

  const value = useMemo(
    () => ({ job, startUpload, dismissBanner }),
    [job, startUpload, dismissBanner]
  );

  return (
    <UploadProgressContext.Provider value={value}>{children}</UploadProgressContext.Provider>
  );
}

export function useUploadProgress() {
  const ctx = useContext(UploadProgressContext);
  if (!ctx) throw new Error("useUploadProgress 需在 UploadProgressProvider 内使用");
  return ctx;
}

export function UploadGlobalBanner() {
  const { job, dismissBanner } = useUploadProgress();
  if (job.phase === "idle") return null;

  const isWorking = job.phase === "uploading" || job.phase === "processing";

  return (
    <div
      role="status"
      aria-live="polite"
      className={`text-sm px-4 py-2.5 border-b flex flex-wrap items-center justify-center gap-3 ${
        job.phase === "error"
          ? "bg-red-500/10 border-red-200 dark:border-red-900 text-red-800 dark:text-red-200"
          : job.phase === "success"
            ? "bg-emerald-500/10 border-emerald-200 dark:border-emerald-900 text-emerald-900 dark:text-emerald-100"
            : "bg-amber-500/12 border-amber-200/80 dark:border-amber-900/50 text-[var(--fg)]"
      }`}
    >
      <span className="text-center">
        {job.phase === "uploading" && (
          <>
            <strong>正在上传</strong>「{job.filename}」…{" "}
            {job.message ? job.message : `${job.progress}%`}
          </>
        )}
        {job.phase === "processing" && (
          <>
            <strong>正在处理</strong>「{job.filename}」… {job.message}
          </>
        )}
        {job.phase === "success" && <>{job.message}</>}
        {job.phase === "error" && (
          <>
            <strong>处理失败</strong>「{job.filename}」：{job.message}
          </>
        )}
      </span>
      {isWorking && (
        <span className="text-xs text-[var(--muted)] max-w-xl text-center">
          可继续浏览其他页面，任务在后台进行；请勿<strong>关闭浏览器标签</strong>
          。关闭或刷新标签可能中断请求。
        </span>
      )}
      {!isWorking && (
        <button
          type="button"
          onClick={dismissBanner}
          className="text-xs underline text-[var(--muted)] hover:text-[var(--fg)]"
        >
          关闭提示
        </button>
      )}
    </div>
  );
}
