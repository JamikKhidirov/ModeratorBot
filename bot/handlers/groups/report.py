from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.database.requests import (
    create_report, get_pending_reports, resolve_report, get_report, get_user, get_chat,
)
from bot.database.models import ReportStatus
from bot.filters.admin import IsAdminFilter
from bot.filters.chat_type import IsGroupFilter, IsPrivateFilter
from bot.keyboards.inline import back_kb

router = Router()


@router.message(Command("report"), IsGroupFilter())
async def cmd_report(message: Message):
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение, на которое хотите пожаловаться.")
        return

    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        await message.answer("❌ Нельзя жаловаться на самого себя.")
        return

    reason = message.text.replace("/report", "", 1).strip() or None

    report = await create_report(
        chat_id=message.chat.id,
        reporter_id=message.from_user.id,
        target_id=target.id,
        message_id=message.reply_to_message.message_id,
        message_text=message.reply_to_message.text or message.reply_to_message.caption or None,
        reason=reason,
    )

    await message.answer(
        f"✅ Жалоба #{report.id} отправлена администраторам!\n"
        f"Причина: {reason or 'Не указана'}"
    )

    await notify_admins_about_report(message, report)


async def notify_admins_about_report(message: Message, report):
    chat = message.chat
    target = message.reply_to_message.from_user if message.reply_to_message else None

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data=f"report_resolve:{report.id}")
    builder.button(text="❌ Отклонить", callback_data=f"report_dismiss:{report.id}")
    builder.button(text="🚫 Забанить", callback_data=f"report_ban:{report.id}")

    text = (
        f"🚨 <b>Новая жалоба #{report.id}</b>\n\n"
        f"<b>Чат:</b> {chat.title}\n"
        f"<b>От:</b> {message.from_user.full_name} (ID: {message.from_user.id})\n"
        f"<b>На:</b> {target.full_name if target else '—'} (ID: {report.target_id})\n"
        f"<b>Причина:</b> {report.reason or 'Не указана'}\n"
        f"<b>Текст сообщения:</b>\n<code>{report.message_text or '—'}</code>"
    )

    from bot.database.requests import get_users_by_role
    from bot.database.models import UserRole
    admins = await get_users_by_role(UserRole.ADMIN)
    superadmins = await get_users_by_role(UserRole.SUPERADMIN)

    for admin in admins + superadmins:
        try:
            await message.bot.send_message(
                admin.id, text, reply_markup=builder.as_markup()
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("report_resolve:"), IsAdminFilter())
async def report_resolve(callback: CallbackQuery):
    report_id = int(callback.data.split(":")[1])
    await resolve_report(report_id, callback.from_user.id, ReportStatus.RESOLVED)
    await callback.message.edit_text(
        callback.message.html_text + "\n\n✅ <b>Жалоба решена</b>",
        reply_markup=None,
    )
    await callback.answer("✅ Жалоба принята", show_alert=True)


@router.callback_query(F.data.startswith("report_dismiss:"), IsAdminFilter())
async def report_dismiss(callback: CallbackQuery):
    report_id = int(callback.data.split(":")[1])
    await resolve_report(report_id, callback.from_user.id, ReportStatus.DISMISSED)
    await callback.message.edit_text(
        callback.message.html_text + "\n\n❌ <b>Жалоба отклонена</b>",
        reply_markup=None,
    )
    await callback.answer("❌ Жалоба отклонена", show_alert=True)


@router.callback_query(F.data.startswith("report_ban:"), IsAdminFilter())
async def report_ban(callback: CallbackQuery):
    report_id = int(callback.data.split(":")[1])
    report = await get_report(report_id)
    if not report:
        return await callback.answer("Жалоба не найдена", show_alert=True)

    await resolve_report(report_id, callback.from_user.id, ReportStatus.RESOLVED)
    try:
        await callback.bot.ban_chat_member(report.chat_id, report.target_id)
    except Exception:
        pass

    await callback.message.edit_text(
        callback.message.html_text + "\n\n🚫 <b>Пользователь забанен</b>",
        reply_markup=None,
    )
    await callback.answer("🚫 Пользователь забанен", show_alert=True)


@router.callback_query(F.data == "admin_reports", IsAdminFilter())
async def admin_reports_list(callback: CallbackQuery):
    reports = await get_pending_reports()
    if not reports:
        await callback.message.edit_text("📭 Нет активных жалоб.", reply_markup=back_kb("admin_panel"))
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for r in reports[:10]:
        builder.button(
            text=f"#{r.id} | {r.target_id} | {r.reason or '—'[:20]}",
            callback_data=f"report_view:{r.id}"
        )
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text("🚨 <b>Активные жалобы:</b>", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("report_view:"), IsAdminFilter())
async def report_view(callback: CallbackQuery):
    report_id = int(callback.data.split(":")[1])
    report = await get_report(report_id)
    if not report:
        await callback.answer("Жалоба не найдена", show_alert=True)
        return

    from bot.database.requests import get_user
    reporter = await get_user(report.reporter_id)
    target = await get_user(report.target_id)

    text = (
        f"🚨 <b>Жалоба #{report.id}</b>\n\n"
        f"<b>Статус:</b> {report.status.value}\n"
        f"<b>Репортёр:</b> {reporter.first_name if reporter else report.reporter_id}\n"
        f"<b>Нарушитель:</b> {target.first_name if target else report.target_id} (ID: {report.target_id})\n"
        f"<b>Причина:</b> {report.reason or 'Не указана'}\n"
        f"<b>Сообщение:</b> {report.message_text or '—'}\n"
        f"<b>ID чата:</b> {report.chat_id}"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if report.status == ReportStatus.PENDING:
        builder.button(text="✅ Принять", callback_data=f"report_resolve:{report.id}")
        builder.button(text="❌ Отклонить", callback_data=f"report_dismiss:{report.id}")
    builder.button(text="🔙 Назад", callback_data="admin_reports")
    builder.adjust(2)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
