import asyncio
import logging

from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import Config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("report-bot")


async def on_startup(bot: Bot, dispatcher: Dispatcher, cfg: Config):
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="ابدأ / Start"),
            BotCommand(command="report", description="إنشاء تقرير / Create"),
        ]
    )
    log.info("Bot commands registered. Ready: %s", cfg.ready)


def build_app() -> FastAPI:
    from handlers import setup_handlers

    cfg = Config()
    app = FastAPI(title="Report Bot")
    app.state.cfg = cfg

    @app.on_event("startup")
    async def startup():
        from aiogram.enums import ParseMode

        if not cfg.ready:
            log.warning("Missing BOT_TOKEN or GEMINI_API_KEY. Bot polling skipped.")
            app.state.bot = None
            app.state.task = None
            return

        bot = Bot(token=cfg.bot_token, default=ParseMode.HTML)
        dp = Dispatcher()
        dp["cfg"] = cfg
        setup_handlers(dp, cfg)

        await on_startup(bot, dp, cfg)

        task = asyncio.create_task(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        )
        app.state.bot = bot
        app.state.task = task
        log.info("Bot polling started")

    @app.on_event("shutdown")
    async def shutdown():
        task = getattr(app.state, "task", None)
        bot = getattr(app.state, "bot", None)
        if task:
            task.cancel()
        if bot:
            await bot.session.close()
        log.info("Bot stopped")

    return app


app = build_app()


@app.get("/")
async def root():
    return {"ok": True, "bot": "report-bot"}


@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)