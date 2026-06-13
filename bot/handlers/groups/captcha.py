import asyncio
import random
import string

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ChatPermissions
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.requests import get_chat_settings, get_or_create_chat

router = Router()

PENDING_CAPTCHA = {}


@router.message(F.new_chat_members)
async def captcha_new_member(message: Message):
    settings = await get_chat_settings(message.chat.id)
    if not settings or not settings.captcha_enabled:
        return

    for member in message.new_chat_members:
        if member.is_bot:
            continue

        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        PENDING_CAPTCHA[member.id] = {"chat_id": message.chat.id, "code": code}

        builder = InlineKeyboardBuilder()
        builder.button(text=f"✅ Я человек ({code})", callback_data=f"captcha:{member.id}:{code}")

        try:
            await message.chat.restrict(
                member.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
        except Exception:
            pass

        sent = await message.answer(
            f"👋 <b>Добро пожаловать, {member.full_name}!</b>\n\n"
            f"Для подтверждения, что вы не бот, нажмите на кнопку ниже в течение 60 секунд.\n"
            f"<i>Код: {code}</i>",
            reply_markup=builder.as_markup(),
        )

        await asyncio.sleep(60)

        if member.id in PENDING_CAPTCHA:
            del PENDING_CAPTCHA[member.id]
            try:
                await message.chat.ban(member.id)
                await message.chat.unban(member.id)
                await sent.edit_text(
                    f"❌ {member.full_name} не прошёл капчу и был кикнут."
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("captcha:"))
async def captcha_pass(callback: CallbackQuery):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    code = parts[2]

    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваша капча!", show_alert=True)
        return

    pending = PENDING_CAPTCHA.get(user_id)
    if not pending:
        await callback.answer("❌ Капча уже недействительна.", show_alert=True)
        return

    if pending["code"] != code:
        await callback.answer("❌ Неверный код.", show_alert=True)
        return

    del PENDING_CAPTCHA[user_id]

    try:
        await callback.message.chat.restrict(
            user_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True,
                can_send_polls=True, can_invite_users=True,
            ),
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ {callback.from_user.full_name}, вы прошли капчу!"
    )
    await callback.answer("✅ Капча пройдена!", show_alert=True)
