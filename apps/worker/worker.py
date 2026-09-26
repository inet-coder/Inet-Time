from arq.connections import RedisSettings

from core.settings import settings
from tasks import activate_automation_job, revoke_account_job, run_automation_once, send_stories_job, stop_automation_job


async def startup(ctx):
    print(f"worker ishga tushdi (mock={settings.mock_telegram})")


async def shutdown(ctx):
    print("worker to'xtadi")


class WorkerSettings:
    functions = [run_automation_once, activate_automation_job, stop_automation_job, revoke_account_job, send_stories_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://redis:6379")
