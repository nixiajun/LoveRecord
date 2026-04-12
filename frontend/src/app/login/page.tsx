"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, setToken } from "@/lib/api";

const schema = z.object({
  email: z.string().email("请输入有效邮箱"),
  password: z.string().min(1, "请输入密码"),
});

type Form = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm<Form>({ resolver: zodResolver(schema) });

  async function onSubmit(data: Form) {
    try {
      const res = await apiFetch<{ access_token: string }>("/api/v1/auth/login", {
        auth: false,
        method: "POST",
        body: JSON.stringify(data),
      });
      setToken(res.access_token);
      router.push("/dashboard");
    } catch {
      setError("root", { message: "登录失败，请检查账号或后端是否启动" });
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-rose-50 to-pink-50/30 dark:from-[#1c1418] dark:to-[#1c1418]">
      <header className="flex justify-between items-center p-4 max-w-5xl mx-auto w-full">
        <div className="flex items-center gap-2">
          <span className="text-lg">💕</span>
          <span className="font-semibold bg-gradient-to-r from-rose-500 to-pink-500 bg-clip-text text-transparent">恋爱记录</span>
        </div>
        <ThemeToggle />
      </header>
      <main className="flex-1 flex items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <p className="text-3xl mb-2">💗</p>
            <CardTitle>欢迎回来</CardTitle>
            <p className="text-xs text-[var(--muted)]">登录你们的恋爱小世界</p>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
              <div>
                <Label htmlFor="email">邮箱</Label>
                <Input id="email" type="email" autoComplete="email" {...register("email")} />
                {errors.email && (
                  <p className="text-xs text-red-500 mt-1">{errors.email.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="password">密码</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  {...register("password")}
                />
                {errors.password && (
                  <p className="text-xs text-red-500 mt-1">{errors.password.message}</p>
                )}
              </div>
              {errors.root && (
                <p className="text-sm text-red-500">{errors.root.message}</p>
              )}
              <Button type="submit" className="w-full">
                进入
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
