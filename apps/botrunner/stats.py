"""Yengil statistika: Redis hisoblagichlari (kun bo'yicha), 100 kun saqlanadi.

Hodisalar: start, page:<id>, cart_add, checkout, order, form:<id>. Voronka va «eng ko'p ochilganlar» shundan chiziladi."""

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import RunningBot, Runner

TTL = 100 * 24 * 3600


def _day(offset: int = 0) -> str:
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=offset)).strftime("%Y%m%d")


def _key(bot: "RunningBot", day: str) -> str:
    return f"ub:{bot.bot_id}:stat:{day}"


async def track(runner: "Runner", bot: "RunningBot", event: str, n: int = 1) -> None:
    if getattr(bot, "sandbox", False):
        return
    key = _key(bot, _day())
    try:
        await runner.redis.hincrby(key, event, n)
        await runner.redis.expire(key, TTL)
    except Exception:  # statistika hech qachon botni to'xtatmasin
        pass


async def collect(runner: "Runner", bot: "RunningBot", days: int = 7) -> dict[str, int]:
    total: dict[str, int] = {}
    for d in range(days):
        raw = await runner.redis.hgetall(_key(bot, _day(d)))
        for k, v in raw.items():
            name = k.decode() if isinstance(k, bytes) else k
            total[name] = total.get(name, 0) + int(v)
    return total


async def per_day(runner: "Runner", bot: "RunningBot", event: str, days: int = 7) -> list[int]:
    out = []
    for d in range(days - 1, -1, -1):
        v = await runner.redis.hget(_key(bot, _day(d)), event)
        out.append(int(v) if v else 0)
    return out


def bar(values: list[int]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    top = max(values) or 1
    return "".join(blocks[min(7, int(v / top * 7))] if v else "·" for v in values)
