"""InetTime AI sifat to'plamini ishga tushirish.

    OPENAI_API_KEY=sk-... python tools/run_bot_eval.py --model gpt-4.1-mini --limit 10 --out eval.md
    python tools/run_bot_eval.py --only salon,flowers --parallel 3

Natija: har bir brif uchun ball va muammolar jadvali (Markdown). Promptlarni o'zgartirgach ball tushmaganini tekshiring."""

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "packages" / "core"))

from core import bot_eval  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--limit", type=int, default=0, help="faqat dastlabki N ta brif")
    ap.add_argument("--only", default="", help="vergul bilan brif id'lari")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    briefs = bot_eval.BRIEFS
    if args.only:
        wanted = set(args.only.split(","))
        briefs = [b for b in briefs if b.id in wanted]
    if args.limit:
        briefs = briefs[: args.limit]
    sem = asyncio.Semaphore(args.parallel)

    async def one(brief):
        async with sem:
            res = await bot_eval.run_brief(args.model, brief)
            print(f"{brief.id:14} {res.score:3}  {res.error or ''}", flush=True)
            return res

    results = await asyncio.gather(*(one(b) for b in briefs))
    report = bot_eval.render_report(list(results), args.model)
    if args.out:
        pathlib.Path(args.out).write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())
