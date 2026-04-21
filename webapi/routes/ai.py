
from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import OpenAI

from ..dependencies.auth import require_user
from ..db.models import User
from ..settings import settings


router = APIRouter(tags=["ai"])


class ContentBlock(BaseModel):
    """消息内容块：文本或图片"""
    type: Literal["text", "image_url"] = "text"
    text: str | None = None
    image_url: dict | None = None  # {"url": "data:image/...;base64,..."}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[ContentBlock] = ""


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., description="对话历史消息列表")
    system_prompt: str | None = Field(
        default=None,
        description="可选的自定义系统提示词",
    )


def _build_openai_client() -> OpenAI:
    """构造指向 ai.td.ee 的 OpenAI 兼容客户端。"""
    kwargs: dict = {
        "base_url": settings.ai_base_url.rstrip("/") + "/v1",
        "api_key": settings.ai_api_key,
    }
    return OpenAI(**kwargs)


def _sse_data(obj: dict) -> str:
    """单行 data 字段：JSON 编码，避免正文中的换行破坏 SSE 帧。"""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/ai/chat")
async def chat(
    req: ChatRequest,
    current_user: User = Depends(require_user),
) -> StreamingResponse:
    """
    流式 AI 对话（SSE）。

    事件均为 JSON，每帧一行 data: {...}\\n\\n
    - {"type": "delta", "text": "..."}  增量文本
    - {"type": "done"}                   流正常结束
    - {"type": "error", "message": "..."} 出错
    """
    system_text = (
        req.system_prompt
        or "你是一个专业的辐射制冷/制热领域的助手，具有充分的物理化学、光学知识，并且具有丰富的辐射制冷/制热领域的经验。用户可能会询问关于辐射制冷、制热、热管理、建筑能耗、材料光学性质等方面的问题。请用中文回答。"
    )

    full_messages: list[dict] = [{"role": "system", "content": system_text}]
    for msg in req.messages:
        if isinstance(msg.content, str):
            full_messages.append({"role": msg.role, "content": msg.content})
        else:
            # 图片+文本多模态消息
            full_messages.append({"role": msg.role, "content": msg.content})

    client = _build_openai_client()

    try:
        stream = client.chat.completions.create(
            model=settings.ai_model,
            messages=full_messages,
            stream=True,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 服务调用失败：{e}",
        )

    async def sse_iterator():
        sent_done = False
        try:
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue

                delta = choices[0].delta
                content = getattr(delta, "content", None)
                if content is None and isinstance(delta, dict):
                    content = delta.get("content")
                if content:
                    yield _sse_data({"type": "delta", "text": content})
                    await asyncio.sleep(0)

                finish_reason = choices[0].finish_reason
                if finish_reason:
                    yield _sse_data({"type": "done"})
                    sent_done = True
                    await asyncio.sleep(0)
                    break
        except Exception as e:
            yield _sse_data({"type": "error", "message": str(e)})
            sent_done = True
        finally:
            if not sent_done:
                yield _sse_data({"type": "done"})
                await asyncio.sleep(0)

    return StreamingResponse(
        sse_iterator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
