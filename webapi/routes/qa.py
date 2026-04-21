from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.models import QaAnswer, QaQuestion, User
from ..db.session import SessionLocal
from ..dependencies.auth import require_user


router = APIRouter(tags=["qa"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class QaQuestionSummary(BaseModel):
    id: int
    title: str
    excerpt: str
    answer_count: int
    author_username: str
    created_at: datetime
    updated_at: datetime


class QaAnswerOut(BaseModel):
    id: int
    body: str
    author_username: str
    created_at: datetime
    updated_at: datetime


class QaQuestionDetail(BaseModel):
    id: int
    title: str
    body: str
    author_username: str
    created_at: datetime
    updated_at: datetime
    answers: List[QaAnswerOut] = Field(default_factory=list)


class CreateQuestionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)


class CreateAnswerRequest(BaseModel):
    body: str = Field(..., min_length=1)


@router.get("/qa/questions", response_model=List[QaQuestionSummary])
def list_questions(
    q: str | None = Query(default=None, description="关键词搜索（可选）"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(_get_db),
) -> List[QaQuestionSummary]:
    query = db.query(QaQuestion).filter(QaQuestion.is_deleted.is_(False))

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(QaQuestion.title.ilike(like) | QaQuestion.body.ilike(like))

    rows: list[QaQuestion] = (
        query.order_by(QaQuestion.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not rows:
        return []

    # 预取作者用户名
    user_ids = {r.created_by_user_id for r in rows}
    users = (
        db.query(User)
        .filter(User.id.in_(user_ids))
        .all()
    )
    user_map = {u.id: u.username for u in users}

    # 统计每个问题的回答数
    question_ids = [r.id for r in rows]
    counts = (
        db.query(QaAnswer.question_id)
        .filter(QaAnswer.question_id.in_(question_ids))
        .with_entities(QaAnswer.question_id)
        .all()
    )
    # 简单计数（避免额外 group_by 复杂度）
    count_map: dict[int, int] = {}
    for (qid,) in counts:
        count_map[qid] = count_map.get(qid, 0) + 1

    def _excerpt(text: str, length: int = 120) -> str:
        s = text.strip().replace("\n", " ")
        return s[:length] + ("..." if len(s) > length else "")

    return [
        QaQuestionSummary(
            id=r.id,
            title=r.title,
            excerpt=_excerpt(r.body),
            answer_count=count_map.get(r.id, 0),
            author_username=user_map.get(r.created_by_user_id, "匿名用户"),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/qa/questions/{question_id}", response_model=QaQuestionDetail)
def get_question(
    question_id: int,
    db: Session = Depends(_get_db),
) -> QaQuestionDetail:
    qrow: QaQuestion | None = db.get(QaQuestion, question_id)
    if not qrow or qrow.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question_not_found")

    user = db.get(User, qrow.created_by_user_id)
    author_username = user.username if user else "匿名用户"

    answers: list[QaAnswer] = (
        db.query(QaAnswer)
        .filter(QaAnswer.question_id == question_id)
        .order_by(QaAnswer.created_at.asc())
        .all()
    )

    # 预取回答作者
    answer_user_ids = {a.created_by_user_id for a in answers}
    answer_users = (
        db.query(User)
        .filter(User.id.in_(answer_user_ids))
        .all()
    )
    answer_user_map = {u.id: u.username for u in answer_users}

    return QaQuestionDetail(
        id=qrow.id,
        title=qrow.title,
        body=qrow.body,
        author_username=author_username,
        created_at=qrow.created_at,
        updated_at=qrow.updated_at,
        answers=[
            QaAnswerOut(
                id=a.id,
                body=a.body,
                author_username=answer_user_map.get(a.created_by_user_id, "匿名用户"),
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in answers
        ],
    )


@router.post("/qa/questions", response_model=QaQuestionDetail)
def create_question(
    req: CreateQuestionRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(_get_db),
) -> QaQuestionDetail:
    now = _now_utc()
    qrow = QaQuestion(
        title=req.title.strip(),
        body=req.body.strip(),
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    db.add(qrow)
    db.commit()
    db.refresh(qrow)

    return QaQuestionDetail(
        id=qrow.id,
        title=qrow.title,
        body=qrow.body,
        author_username=current_user.username,
        created_at=qrow.created_at,
        updated_at=qrow.updated_at,
        answers=[],
    )


@router.post("/qa/questions/{question_id}/answers", response_model=QaAnswerOut)
def create_answer(
    question_id: int,
    req: CreateAnswerRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(_get_db),
) -> QaAnswerOut:
    qrow: QaQuestion | None = db.get(QaQuestion, question_id)
    if not qrow or qrow.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question_not_found")

    now = _now_utc()
    ans = QaAnswer(
        question_id=question_id,
        body=req.body.strip(),
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(ans)

    # 更新问题的 updated_at，方便排序
    qrow.updated_at = now

    db.commit()
    db.refresh(ans)

    return QaAnswerOut(
        id=ans.id,
        body=ans.body,
        author_username=current_user.username,
        created_at=ans.created_at,
        updated_at=ans.updated_at,
    )

