from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.loader import config
from bot.keyboards.inline import register_kb, back_kb
from bot.keyboards.reply import main_menu_kb, remove_kb
from bot.utils.texts import START_TEXT, HELP_TEXT, PROFILE_TEXT
from bot.database.requests import get_user, get_warnings_count, get_user_ads

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db_user):
    await message.answer(
        START_TEXT,
        reply_markup=register_kb(),
    )


@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def cmd_help(event: Message | CallbackQuery):
    text = HELP_TEXT
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_kb("start"))
        await event.answer()
    else:
        await event.answer(text)


@router.callback_query(F.data == "start")
async def back_to_start(callback: CallbackQuery):
    await callback.message.edit_text(START_TEXT, reply_markup=register_kb())
    await callback.answer()


@router.callback_query(F.data == "profile")
@router.message(F.text == "👤 Профиль")
async def show_profile(event: Message | CallbackQuery, db_user):
    warns = await get_warnings_count(db_user.id, 0)
    ads = await get_user_ads(db_user.id)
    text = PROFILE_TEXT.format(
        user_id=db_user.id,
        first_name=db_user.first_name or "—",
        username=db_user.username or "—",
        role=db_user.role.value,
        balance=db_user.balance or 0,
        warns=warns,
        ads_count=len(ads),
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_kb("start"))
        await event.answer()
    else:
        await event.answer(text, reply_markup=register_kb())


@router.message(F.text == "❓ Помощь")
async def help_reply(message: Message):
    await message.answer(HELP_TEXT, reply_markup=register_kb())
