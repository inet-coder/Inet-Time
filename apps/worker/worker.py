from arq import cron
from arq.connections import RedisSettings

from core.settings import settings


async def startup(ctx):
    print("worker ishga tushdi (skeleton)")


async def shutdown(ctx):
    print("worker to'xtadi")


async def noop(ctx):
    return "ok"


class WorkerSettings:
    functions = [noop]
    cron_jobs = [cron(noop, minute=set(range(0, 60, 5)))]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://redis:6379")
