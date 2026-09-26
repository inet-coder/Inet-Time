"""AI (OpenAI) — avto-javob va matn yozish. Promptlar ataylab qisqa: har chaqiruv arzon bo'lsin.

Xarajat nazorati: tarif bo'yicha kunlik limit (Redis hisoblagich), har chaqiruv ai_usage'ga yoziladi,
javob uzunligi max_completion_tokens bilan cheklangan."""

import datetime
import json
import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import AIUsage, SystemSetting
from core.settings import settings

logger = logging.getLogger(__name__)

AI_SETTING_KEY = "ai"
MAX_STYLE_LEN = 300
MAX_CONTEXT_MESSAGES = 6
MAX_CONTEXT_CHARS = 300
REPLY_MAX_TOKENS = 120
SUGGEST_MAX_TOKENS = 400

# (kirish $, chiqish $) 1M token uchun — taxminiy, admin paneldagi xarajat hisobi uchun. None — narx noma'lum.
MODELS: dict[str, tuple[float, float] | None] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5.4-nano": None,
    "gpt-5.4-mini": None,
}

# 3–4 ta tayyor uslub. Qisqa — system promptga to'g'ridan-to'g'ri qo'shiladi.
# title/desc — foydalanuvchiga (o'zbekcha); prompt — modelga ichki ko'rsatma (inglizcha: model uni javob matni
# sifatida takrorlamaydi va suhbatdosh tiliga aniqroq moslashadi).
PRESETS: dict[str, dict[str, str]] = {
    "busy": {
        "title": "⏳ Bandman",
        "desc": "Bandligingizni, xabarni ko'rganingizni va keyinroq o'zingiz javob berishingizni aytadi.",
        "prompt": "Say the owner is busy right now, has seen the message and will reply later. One sentence.",
    },
    "friendly": {
        "title": "🙂 Do'stona",
        "desc": "Samimiy va iliq, mos emoji bilan.",
        "prompt": "Warm and friendly, with a fitting emoji.",
    },
    "formal": {
        "title": "💼 Rasmiy",
        "desc": "Hurmat bilan, «Siz» deb, emoji'siz.",
        "prompt": "Polite and formal, no emoji.",
    },
    "fun": {
        "title": "😄 Hazilkash",
        "desc": "Yengil hazil bilan, lekin hurmatli.",
        "prompt": "Light humor, friendly but respectful.",
    },
}
DEFAULT_PRESET = "busy"

# Qoidalar inglizcha — model ularga aniqroq amal qiladi; javob tili esa suhbatdoshniki.
_REPLY_SYSTEM = (
    "You auto-reply to Telegram private messages on behalf of {name}. Style: {style}\n"
    "Rules: reply ONLY in the language of the last incoming message (English -> English, Russian -> Russian, "
    "Uzbek -> Uzbek), even though this prompt is mixed; 1-2 short sentences; you are an "
    "auto-reply, not an assistant — never offer help or ask how you can help; never promise anything, agree to "
    "meetings or money, or share personal info — say {name} will reply personally; if asked whether you are a "
    "bot, say this is an auto-reply."
)

_SUGGEST_FIELDS = {
    "bio": ("Telegram bio", 70),
    "name": ("Telegram ism", 40),
    "playlist": ("Telegram bio", 70),
}


class AIError(Exception):
    """Foydalanuvchiga ko'rsatsa bo'ladigan AI xatosi."""


@dataclass
class AIResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


# --- Sozlamalar ---


async def get_config(db: AsyncSession) -> dict:
    row = await db.scalar(select(SystemSetting).where(SystemSetting.key == AI_SETTING_KEY))
    value = row.value if row is not None else {}
    model = value.get("model") or settings.openai_model
    return {
        "model": model,
        "enabled": bool(value.get("enabled", True)),
        "configured": bool(settings.openai_api_key),
    }


async def ensure_available(db: AsyncSession) -> dict:
    config = await get_config(db)
    if not config["configured"]:
        raise AIError("AI hali sozlanmagan (admin OpenAI kalitini qo'shishi kerak)")
    if not config["enabled"]:
        raise AIError("AI vaqtincha o'chirilgan")
    return config


def style_prompt(preset: str, style: str | None) -> str:
    if preset == "custom" and style and style.strip():
        return style.strip()[:MAX_STYLE_LEN]
    return PRESETS.get(preset, PRESETS[DEFAULT_PRESET])["prompt"]


# --- Kunlik limit ---


def _quota_key(user_id: int) -> str:
    today = datetime.datetime.now(ZoneInfo(settings.default_timezone)).strftime("%Y%m%d")
    return f"ai:used:{user_id}:{today}"


async def used_today(redis, user_id: int) -> int:
    value = await redis.get(_quota_key(user_id))
    return int(value) if value else 0


async def take_quota(redis, user_id: int, limit: int) -> bool:
    """Atomik: limitdan oshsa qaytarib oladi va False."""
    if limit <= 0:
        return False
    key = _quota_key(user_id)
    used = await redis.incr(key)
    if used == 1:
        await redis.expire(key, 2 * 86400)
    if used > limit:
        await redis.decr(key)
        return False
    return True


async def refund_quota(redis, user_id: int) -> None:
    await redis.decr(_quota_key(user_id))


# --- OpenAI chaqiruvi ---

_client: AsyncOpenAI | None = None


def _openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=1)
    return _client


async def _complete(model: str, messages: list[dict], max_tokens: int, json_mode: bool = False) -> AIResult:
    params: dict = {"model": model, "messages": messages, "max_completion_tokens": max_tokens}
    if model.startswith("gpt-5"):
        # Reasoning modellar: fikrlashni minimal qilamiz — tez va arzon, oddiy chat uchun yetarli.
        params["reasoning_effort"] = "minimal"
        params["max_completion_tokens"] = max_tokens + 200
    else:
        params["temperature"] = 0.7
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    try:
        resp = await _openai().chat.completions.create(**params)
    except OpenAIError as exc:
        logger.warning("OpenAI xatosi: %s", exc)
        raise AIError("AI javob bermadi, keyinroq urinib ko'ring") from exc
    text = (resp.choices[0].message.content or "").strip()
    usage = resp.usage
    return AIResult(
        text=text,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        model=model,
    )


async def log_usage(db: AsyncSession, user_id: int, kind: str, result: AIResult) -> None:
    db.add(
        AIUsage(
            user_id=user_id, kind=kind, model=result.model,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )
    )
    await db.commit()


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = MODELS.get(model)
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


# --- Xizmatlar ---


async def reply(model: str, owner_name: str, preset: str, style: str | None, history: list[tuple[bool, str]]) -> AIResult:
    """history: [(egasi_yozganmi, matn), ...] eskidan yangiga. Oxirgisi — javob beriladigan xabar."""
    system = _REPLY_SYSTEM.format(name=owner_name or "Egasi", style=style_prompt(preset, style))
    messages = [{"role": "system", "content": system}]
    for mine, text in history[-MAX_CONTEXT_MESSAGES:]:
        messages.append({"role": "assistant" if mine else "user", "content": text[:MAX_CONTEXT_CHARS]})
    return await _complete(model, messages, REPLY_MAX_TOKENS)


async def suggest(model: str, field: str, topic: str) -> tuple[list, AIResult]:
    """Studiya uchun 5 ta variant. schedule — [{time, text}], qolganlari — [matn]."""
    topic = topic.strip()[:200] or "umumiy, ijobiy kayfiyat"
    if field == "schedule":
        prompt = (
            f"Mavzu: {topic}. Kun davomida 4 ta vaqt uchun Telegram bio yoz (har biri 50 belgidan qisqa, mos emoji bilan). "
            'Mavzu tilida. Faqat JSON: {"items": [{"time": "09:00", "text": "..."}]}'
        )
    else:
        what, limit = _SUGGEST_FIELDS.get(field, _SUGGEST_FIELDS["bio"])
        prompt = (
            f"Mavzu: {topic}. {what} uchun 5 ta turli variant yoz. Har biri QISQA: {limit - 20} belgigacha, "
            'mos emoji bilan. Mavzu tilida. Faqat JSON: {"items": ["...", "..."]}'
        )
    result = await _complete(model, [{"role": "user", "content": prompt}], SUGGEST_MAX_TOKENS, json_mode=True)
    try:
        items = json.loads(result.text).get("items", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        raise AIError("AI javobini o'qib bo'lmadi, qaytadan urinib ko'ring") from exc
    if field == "schedule":
        items = [
            {"time": str(i.get("time", ""))[:5], "text": str(i.get("text", "")).strip()[:70]}
            for i in items
            if isinstance(i, dict) and i.get("text")
        ][:6]
    else:
        limit = _SUGGEST_FIELDS.get(field, _SUGGEST_FIELDS["bio"])[1]
        # Uzunlarini kesmaymiz (so'z o'rtasida qoladi) — tashlab yuboramiz.
        items = [str(i).strip() for i in items if 0 < len(str(i).strip()) <= limit][:5]
    return items, result


async def test(model: str) -> AIResult:
    return await _complete(model, [{"role": "user", "content": "Bir so'z bilan javob ber: salom"}], 20)
