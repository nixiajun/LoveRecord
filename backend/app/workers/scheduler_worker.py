from __future__ import annotations
"""独立进程：APScheduler 定时任务——每日简报生成 + 推送微信。"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings
from app.database import SessionLocal
from app.models.couple import Couple
from app.services.openclaw.openclaw_push_service import OpenClawPushService
from app.services.summary.summary_service import generate_or_refresh_daily_summary
from app.services.core.timekeys import to_day_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("loverecord.scheduler")


def job_refresh_today_summary() -> None:
    """为默认 couple 刷新「今天」简报（便于定时对接微信推送）。"""
    now = datetime.now(timezone.utc)
    logger.info("定时任务开始执行，UTC 时间: %s", now.isoformat())
    db = SessionLocal()
    try:
        c = db.get(Couple, settings.openclaw_default_couple_id)
        if not c:
            logger.warning("无默认 couple (id=%s)，跳过", settings.openclaw_default_couple_id)
            return
        today = to_day_key(now, c.timezone, c.day_start_hour)
        logger.info("couple_id=%s timezone=%s day_key=%s", c.id, c.timezone, today)
        generate_or_refresh_daily_summary(db, c.id, today)
        db.commit()
        logger.info("已刷新简报 day_key=%s couple_id=%s", today, c.id)

        # 记录活动日志
        try:
            from app.services.core.activity_log import log_activity
            log_activity(
                db, couple_id=c.id,
                action="daily_summary_refresh", category="summary",
                summary=f"定时刷新 {today} 每日简报",
                source="scheduler",
            )
            db.commit()
        except Exception as e:
            logger.warning("活动日志写入失败: %s", e)

        if settings.openclaw_enable_scheduler_push:
            txt = f"LoveRecord：{today} 每日简报已在后台刷新，可打开网页或微信 bot 查看。"
            OpenClawPushService().push_text_to_both(txt, event="loverecord.scheduler.daily_summary_refreshed")
    except Exception as e:
        logger.error("定时任务执行失败: %s", e, exc_info=True)
    finally:
        db.close()


def main() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    sched = BlockingScheduler(timezone=tz)
    sched.add_job(job_refresh_today_summary, "cron", hour=8, minute=0)
    sched.add_job(job_refresh_today_summary, "interval", hours=1)
    logger.info("APScheduler 已启动（每日 8:00 + 每 1h 刷新）")
    sched.start()


if __name__ == "__main__":
    main()
