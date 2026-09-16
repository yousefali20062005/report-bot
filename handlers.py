import asyncio
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from docx_builder import build_docx, preview_text
from gemini_client import generate_report

router = Router()

T = {
    "ar": {
        "welcome": "أهلا 🌟 أنا بوت التقارير الجامعية.\nاضغط `إنشاء تقرير` وأرسل الموضوع، وأولّد لك تقريراً منسّقاً جاهزاً للتقديم.",
        "create": "📝 إنشاء تقرير",
        "lang": "🌐 اللغة",
        "send_topic": "أرسل **موضوع التقرير** (وممكن تضيف تفاصيل إضافية):",
        "choose_pages": "كم عدد الصفحات؟",
        "pages": "صفحات",
        "custom": "✍️ أخرى",
        "send_pages": "أرسل عدد الصفحات (رقم من 1 إلى 50):",
        "bad_pages": "⚠️ أرسل رقماً صحيحاً من 1 إلى 50.",
        "generating": "⏳ جاري توليد التقرير… خذ نفساً.",
        "done": "✅ تم توليد التقرير! المرفق يحوي النسخة المنسّقة.",
        "error": "⚠️ صار خطأ أثناء التوليد. جرّب بعد لحظات.",
        "need_key": "⚠️ البوت مو متهيأ بعد (ناقص مفتاح). تواصل مع المشرف.",
        "cooldown": "⏱️ لحظة… انتظر {s} ثانية قبل طلب جديد.",
        "menu": "اختر من القائمة 👇",
        "lang_set": "اللغة صارت العربية 🇮🇶",
    },
    "en": {
        "welcome": "Hi 🌟 I am the University Report Bot.\nPress `Create Report`, send me a topic, and I will produce a formatted, ready-to-submit report.",
        "create": "📝 Create Report",
        "lang": "🌐 Language",
        "send_topic": "Send the **report topic** (you may add extra details):",
        "choose_pages": "How many pages?",
        "pages": "pages",
        "custom": "✍️ Custom",
        "send_pages": "Send the number of pages (1-50):",
        "bad_pages": "⚠️ Please send a number from 1 to 50.",
        "generating": "⏳ Generating the report… hold on.",
        "done": "✅ Report ready! The attachment holds the formatted version.",
        "error": "⚠️ Something went wrong. Please try again in a moment.",
        "need_key": "⚠️ Bot is not configured yet (missing key). Contact the admin.",
        "cooldown": "⏱️ Please wait {s} seconds before the next request.",
        "menu": "Pick from the menu 👇",
        "lang_set": "Language switched to English 🇬🇧",
    },
}


class ReportFlow(StatesGroup):
    waiting_topic = State()
    waiting_pages = State()


_cfg: Config | None = None
user_lang: dict[int, str] = {}
last_generation: dict[int, float] = {}


def t(user_id: int, key: str, lang: str | None = None, **fmt) -> str:
    lng = lang or user_lang.get(user_id, "ar")
    return T[lng][key].format(**fmt)


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    is_ar = user_lang.get(user_id, "ar") == "ar"
    toggle = "EN" if is_ar else "AR"
    kb = [
        [InlineKeyboardButton(text=t(user_id, "create"), callback_data="create")],
        [InlineKeyboardButton(text=t(user_id, "lang") + f" → {toggle}", callback_data="toggle_lang")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def pages_menu(user_id: int) -> InlineKeyboardMarkup:
    lbl = lambda n: f"{n} {t(user_id, 'pages')}"
    kb = [
        [InlineKeyboardButton(text=lbl(3), callback_data="pages:3"),
         InlineKeyboardButton(text=lbl(5), callback_data="pages:5")],
        [InlineKeyboardButton(text=lbl(8), callback_data="pages:8"),
         InlineKeyboardButton(text=lbl(10), callback_data="pages:10")],
        [InlineKeyboardButton(text=t(user_id, "custom"), callback_data="pages:custom")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_lang.setdefault(message.from_user.id, "ar")
    await message.answer(t(message.from_user.id, "welcome"), reply_markup=main_menu(message.from_user.id))


@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ReportFlow.waiting_topic)
    await message.answer(t(message.from_user.id, "send_topic"))


@router.callback_query(F.data == "toggle_lang")
async def toggle_lang(cq: CallbackQuery):
    cur = user_lang.get(cq.from_user.id, "ar")
    new = "en" if cur == "ar" else "ar"
    user_lang[cq.from_user.id] = new
    await cq.answer()
    await cq.message.edit_text(t(cq.from_user.id, "welcome", new), reply_markup=main_menu(cq.from_user.id))


@router.callback_query(F.data == "create")
async def cb_create(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ReportFlow.waiting_topic)
    await cq.answer()
    await cq.message.edit_text(t(cq.from_user.id, "send_topic"), reply_markup=None)


@router.message(ReportFlow.waiting_topic)
async def got_topic(message: Message, state: FSMContext):
    topic = (message.text or "").strip()
    if not topic:
        await message.answer(t(message.from_user.id, "send_topic"))
        return
    await state.update_data(topic=topic)
    await state.set_state(ReportFlow.waiting_pages)
    await message.answer(t(message.from_user.id, "choose_pages"), reply_markup=pages_menu(message.from_user.id))


@router.callback_query(F.data.startswith("pages:"))
async def cb_pages(cq: CallbackQuery, state: FSMContext):
    value = cq.data.split(":", 1)[1]
    await cq.answer()
    if value == "custom":
        await state.set_state(ReportFlow.waiting_pages)
        await cq.message.answer(t(cq.from_user.id, "send_pages"))
        return
    await start_report(cq.message, state, int(value), cq.from_user.id)
    await cq.message.delete()


@router.message(ReportFlow.waiting_pages)
async def got_pages(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 50):
        await message.answer(t(message.from_user.id, "bad_pages"))
        return
    await start_report(message, state, int(text), message.from_user.id)


@router.message(Command("debug"))
async def cmd_debug(message: Message):
    uid = message.from_user.id
    if _cfg and _cfg.admin_ids and uid not in _cfg.admin_ids:
        return
    if not _cfg:
        await message.answer("Not configured.")
        return
    await message.answer(
        f"BOT_TOKEN: {'✅' if _cfg.bot_token else '❌'}\n"
        f"GEMINI_KEY: {'✅' if _cfg.gemini_api_key else '❌'}\n"
        f"MODEL: {_cfg.gemini_model}\nREADY: {_cfg.ready}"
    )


@router.message()
async def fallback(message: Message):
    await message.answer(t(message.from_user.id, "menu"), reply_markup=main_menu(message.from_user.id))


async def start_report(message: Message, state: FSMContext, pages: int, user_id: int):
    if not _cfg or not _cfg.ready:
        await message.answer(t(user_id, "need_key"))
        return
    now = time.monotonic()
    remaining = 20 - int(now - last_generation.get(user_id, 0))
    if remaining > 0:
        await message.answer(t(user_id, "cooldown", s=remaining))
        return
    last_generation[user_id] = now

    data = await state.get_data()
    topic = data.get("topic", "")
    lang = user_lang.get(user_id, "ar")
    await state.clear()

    wait = await message.answer(t(user_id, "generating"))
    try:
        result = await asyncio.to_thread(generate_report, _cfg, topic, pages, lang)
    except Exception:
        await wait.edit_text(t(user_id, "error"))
        return

    try:
        doc_bytes = build_docx(result, lang)
        filename = ((result.get("title") or "report")[:60]).replace("\\", "_").replace("/", "_") + ".docx"
        await message.answer_document(
            BufferedInputFile(doc_bytes, filename=filename),
            caption=t(user_id, "done"),
        )
        preview = preview_text(result)
        if preview:
            await message.answer(preview[:3900])
    except Exception:
        await message.answer(t(user_id, "error"))
        return

    await message.answer(t(user_id, "menu"), reply_markup=main_menu(user_id))


def setup_handlers(dp, cfg: Config):
    global _cfg
    _cfg = cfg
    dp.include_router(router)