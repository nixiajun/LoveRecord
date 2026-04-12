"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";

type Memorial = {
  id: number;
  title: string;
  occurred_at: string;
  notes: string | null;
  sort_order: number;
};

const schema = z.object({
  title: z.string().min(1, "请填写标题"),
  occurred_at: z.string().min(1, "请选择日期时间"),
  notes: z.string().optional(),
  sort_order: z.coerce.number().int().default(0),
});

type Form = z.infer<typeof schema>;

function toIsoFromDatetimeLocal(v: string) {
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) throw new Error("无效时间");
  return d.toISOString();
}

export default function MemorialsPage() {
  const qc = useQueryClient();
  const { data: list, isLoading } = useQuery({
    queryKey: ["memorials"],
    queryFn: () => apiFetch<Memorial[]>("/api/v1/memorials"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { sort_order: 0 },
  });

  const create = useMutation({
    mutationFn: (body: { title: string; occurred_at: string; notes?: string; sort_order: number }) =>
      apiFetch<Memorial>("/api/v1/memorials", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memorials"] });
      reset({ title: "", occurred_at: "", notes: "", sort_order: 0 });
    },
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/api/v1/memorials/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memorials"] }),
  });

  function onSubmit(data: Form) {
    const occurred_at = toIsoFromDatetimeLocal(data.occurred_at);
    create.mutate({
      title: data.title,
      occurred_at,
      notes: data.notes?.trim() || undefined,
      sort_order: data.sort_order ?? 0,
    });
  }

  if (isLoading) return <p className="text-[var(--muted)]">加载中…</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">纪念日</h1>

      <Card>
        <CardHeader>
          <CardTitle>添加纪念日</CardTitle>
          <p className="text-sm text-[var(--muted)]">
            时间按你本机时区选择，会保存为 UTC 并在全站一致展示。
          </p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4 max-w-md" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <Label htmlFor="title">标题</Label>
              <Input id="title" placeholder="例如：在一起、第一次见面" {...register("title")} />
              {errors.title && <p className="text-xs text-red-500 mt-1">{errors.title.message}</p>}
            </div>
            <div>
              <Label htmlFor="occurred_at">日期与时间</Label>
              <Input id="occurred_at" type="datetime-local" {...register("occurred_at")} />
              {errors.occurred_at && (
                <p className="text-xs text-red-500 mt-1">{errors.occurred_at.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="notes">备注（可选）</Label>
              <Input id="notes" {...register("notes")} />
            </div>
            <div>
              <Label htmlFor="sort_order">排序（数字越小越靠前）</Label>
              <Input id="sort_order" type="number" {...register("sort_order")} />
            </div>
            {create.isError && (
              <p className="text-sm text-red-500">
                {(create.error as Error)?.message || "添加失败"}
              </p>
            )}
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "保存中…" : "保存"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>已有纪念日</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {(list?.length ?? 0) === 0 && <p className="text-[var(--muted)]">暂无</p>}
          {list?.map((m) => (
            <div
              key={m.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] p-3"
            >
              <div>
                <p className="font-medium">{m.title}</p>
                <p className="text-xs text-[var(--muted)]">{new Date(m.occurred_at).toLocaleString()}</p>
                {m.notes && <p className="text-[var(--muted)] mt-1">{m.notes}</p>}
              </div>
              <Button
                type="button"
                variant="outline"
                className="shrink-0 text-red-500 border-red-200 dark:border-red-900"
                disabled={del.isPending}
                onClick={() => {
                  if (confirm(`删除「${m.title}」？`)) del.mutate(m.id);
                }}
              >
                删除
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
