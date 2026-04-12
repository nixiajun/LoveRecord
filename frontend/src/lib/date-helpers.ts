/** 本地日历 YYYY-MM-DD（用于 date input） */
export function toYMDLocal(d: Date): string {
  return d.toLocaleDateString("en-CA");
}

export function addDays(d: Date, delta: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + delta);
  return x;
}

/** 默认「过去 7 天」闭区间：结束日为今天 */
export function defaultWeekRangeRef(): { start: string; end: string } {
  const end = new Date();
  const start = addDays(end, -6);
  return { start: toYMDLocal(start), end: toYMDLocal(end) };
}

/** 当月首尾（本地月） */
export function defaultMonthRangeRef(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { start: toYMDLocal(start), end: toYMDLocal(end) };
}
