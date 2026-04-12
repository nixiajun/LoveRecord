from __future__ import annotations
"""种子数据：admin + partner + 一个 couple。MVP 不开放注册。

密码优先读环境变量 SEED_ADMIN_PASSWORD / SEED_PARTNER_PASSWORD（勿在生产使用默认值）。
"""

import os

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.couple import Couple
from app.models.user import User

_ADMIN_EMAIL = "admin@example.local"
_PARTNER_EMAIL = "partner@example.local"


def run() -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == _ADMIN_EMAIL).first():
            print("Seed 已存在，跳过。")
            return

        admin_pw = os.environ.get("SEED_ADMIN_PASSWORD", "changeme-dev-only")
        partner_pw = os.environ.get("SEED_PARTNER_PASSWORD", "changeme-dev-only")

        admin = User(
            email=_ADMIN_EMAIL,
            password_hash=hash_password(admin_pw),
            display_name="管理员",
            role="admin",
        )
        partner = User(
            email=_PARTNER_EMAIL,
            password_hash=hash_password(partner_pw),
            display_name="另一半",
            role="member",
        )
        db.add_all([admin, partner])
        db.flush()

        couple = Couple(
            name="我们的小宇宙",
            owner_user_id=admin.id,
            partner_user_id=partner.id,
            timezone="Asia/Shanghai",
            status="active",
        )
        db.add(couple)
        db.commit()
        print("Seed 完成（生产环境请设置 SEED_* 强密码，勿提交 .env）：")
        print(f"  {_ADMIN_EMAIL}")
        print(f"  {_PARTNER_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
