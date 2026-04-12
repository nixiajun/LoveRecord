"""情侣检索上下文：双方 user、昵称集合（用于 speaker_role → SQL name IN）。"""

from __future__ import annotations
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.couple import Couple
from app.models.user import User


def _aliases_of(u: User) -> list[str]:
    raw = u.chat_aliases
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _name_set(u: User) -> set[str]:
    s = {u.display_name.strip()} if u.display_name else set()
    s.update(_aliases_of(u))
    return {x for x in s if x}


def display_name_aliases_set(user: User | None) -> set[str]:
    """用于入库时判断昵称属于 owner 还是 partner（与 RAG 检索侧昵称集合一致）。"""
    if user is None:
        return set()
    return _name_set(user)


@dataclass
class RetrievalContext:
    couple: Couple
    couple_id: int
    owner: User
    partner: User | None
    self_user_id: int
    self_names: frozenset[str]
    partner_names: frozenset[str]
    timezone: str


def build_retrieval_context(db: Session, couple: Couple, current_user_id: int) -> RetrievalContext:
    owner = db.get(User, couple.owner_user_id)
    if owner is None:
        raise RuntimeError("owner missing")
    partner = db.get(User, couple.partner_user_id) if couple.partner_user_id else None

    if current_user_id == owner.id:
        self_u, other_u = owner, partner
    elif partner and current_user_id == partner.id:
        self_u, other_u = partner, owner
    else:
        self_u, other_u = owner, partner

    self_names = _name_set(self_u)
    partner_names = _name_set(other_u) if other_u else frozenset()

    return RetrievalContext(
        couple=couple,
        couple_id=couple.id,
        owner=owner,
        partner=partner,
        self_user_id=self_u.id,
        self_names=frozenset(self_names),
        partner_names=frozenset(partner_names),
        timezone=couple.timezone or "Asia/Shanghai",
    )
