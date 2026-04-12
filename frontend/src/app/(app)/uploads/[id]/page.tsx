"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type UploadDetail = {
  id: number;
  couple_id: number;
  uploaded_by: number;
  uploaded_by_display_name: string;
  source_type: string;
  original_filename: string;
  file_path: string;
  upload_date: string;
  parse_status: string;
  parse_error: string | null;
  raw_text_excerpt: string | null;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  affected_day_keys: string[];
};

function fmtTime(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function UploadDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { data, error, isLoading } = useQuery({
    queryKey: ["upload", id],
    queryFn: () => apiFetch<UploadDetail>(`/api/v1/uploads/${id}`),
    enabled: !!id && !Number.isNaN(Number(id)),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/uploads">
          <Button type="button" variant="outline">
            ← 上传历史
          </Button>
        </Link>
        <h1 className="text-2xl font-semibold">上传详情 #{id}</h1>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted)]">加载中…</p>}
      {error && (
        <p className="text-sm text-red-500 whitespace-pre-wrap">
          {(error as Error).message}
        </p>
      )}

      {data && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>文件与状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row k="文件名" v={data.original_filename} />
              <Row k="解析类型" v={data.source_type} />
              <Row k="上传日历日" v={data.upload_date} />
              <Row k="解析状态" v={data.parse_status} />
              <Row k="上传者" v={data.uploaded_by_display_name} />
              <Row k="创建时间" v={fmtTime(data.created_at)} />
              <Row k="更新时间" v={fmtTime(data.updated_at)} />
              <div className="pt-2">
                <span className="text-[var(--muted)]">存储路径 · </span>
                <code className="text-xs break-all">{data.file_path}</code>
              </div>
              {data.parse_error && (
                <div className="pt-2 rounded-lg bg-red-500/10 border border-red-500/20 p-3">
                  <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">
                    解析错误
                  </p>
                  <pre className="text-xs whitespace-pre-wrap">{data.parse_error}</pre>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>导入结果</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                本批次写入消息 <strong>{data.message_count}</strong> 条
                {data.affected_day_keys.length > 0
                  ? `，涉及 ${data.affected_day_keys.length} 个日历日。`
                  : "。"}
              </p>
              {data.affected_day_keys.length > 0 && (
                <ul className="flex flex-wrap gap-2">
                  {data.affected_day_keys.map((dk) => (
                    <li key={dk}>
                      <Link
                        href={`/days/${dk}`}
                        className="inline-flex items-center rounded-full border border-[var(--border)] px-3 py-1 text-xs hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
                      >
                        {dk}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {data.raw_text_excerpt && (
            <Card>
              <CardHeader>
                <CardTitle>原文节选（前约 2000 字）</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs whitespace-pre-wrap break-words max-h-[420px] overflow-auto rounded-lg bg-black/[0.03] dark:bg-white/[0.05] p-3">
                  {data.raw_text_excerpt}
                </pre>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <p>
      <span className="text-[var(--muted)]">{k} · </span>
      {v}
    </p>
  );
}
