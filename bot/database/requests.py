from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.sql import Select

from bot.database.base import get_session
from bot.loader import config
from bot.database.models import (
    User, Chat, ChatSettings, Warning, Punishment,
    Advertisement, GroupModerator, Report, WordTrigger, MessageCount,
    ScheduledMessage, RecurringPost, RssFeed, Payment, AutoDeleteMessage, ChatAdmin,
    Giveaway, GiveawayParticipant,
    UserRole, PunishmentType, AdStatus, ReportStatus, TriggerAction, ScheduledStatus,
)


async def get_or_create_user(
    user_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
) -> User:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            role = UserRole.SUPERADMIN if user_id in config.admin_ids else UserRole.USER
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            changed = False
            if username and user.username != username:
                user.username = username; changed = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name; changed = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name; changed = True
            if user_id in config.admin_ids and user.role != UserRole.SUPERADMIN:
                user.role = UserRole.SUPERADMIN
                changed = True
            if changed:
                await session.commit()
        return user


async def get_or_create_chat(
    chat_id: int,
    title: str = None,
    chat_type: str = None,
    username: str = None,
) -> Chat:
    async with get_session() as session:
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if not chat:
            chat = Chat(
                id=chat_id,
                title=title,
                type=chat_type or "group",
                username=username,
            )
            session.add(chat)
            await session.commit()
            await session.refresh(chat)
        return chat


async def get_user(user_id: int) -> Optional[User]:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def get_chat(chat_id: int) -> Optional[Chat]:
    async with get_session() as session:
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        return result.scalar_one_or_none()


async def update_user_role(user_id: int, role: UserRole) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(role=role)
        )
        await session.commit()


async def update_chat_settings(chat_id: int, **kwargs) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(ChatSettings).where(ChatSettings.chat_id == chat_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            settings = ChatSettings(chat_id=chat_id, **kwargs)
            session.add(settings)
        else:
            for key, value in kwargs.items():
                setattr(settings, key, value)
        await session.commit()


async def get_chat_settings(chat_id: int) -> Optional[ChatSettings]:
    async with get_session() as session:
        result = await session.execute(
            select(ChatSettings).where(ChatSettings.chat_id == chat_id)
        )
        return result.scalar_one_or_none()


async def add_warning(
    user_id: int, chat_id: int, moderator_id: int, reason: str = None
) -> int:
    async with get_session() as session:
        warning = Warning(
            user_id=user_id,
            chat_id=chat_id,
            moderator_id=moderator_id,
            reason=reason,
        )
        session.add(warning)
        await session.commit()

        count_result = await session.execute(
            select(func.count(Warning.id)).where(
                and_(Warning.user_id == user_id, Warning.chat_id == chat_id)
            )
        )
        return count_result.scalar()


async def clear_warnings(user_id: int, chat_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            delete(Warning).where(
                and_(Warning.user_id == user_id, Warning.chat_id == chat_id)
            )
        )
        await session.commit()


async def get_warnings_count(user_id: int, chat_id: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(func.count(Warning.id)).where(
                and_(Warning.user_id == user_id, Warning.chat_id == chat_id)
            )
        )
        return result.scalar()


async def add_punishment(
    user_id: int,
    chat_id: int,
    moderator_id: int,
    ptype: PunishmentType,
    duration: int = None,
    reason: str = None,
) -> Punishment:
    async with get_session() as session:
        expires_at = None
        if duration:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration)
        pun = Punishment(
            user_id=user_id,
            chat_id=chat_id,
            moderator_id=moderator_id,
            type=ptype,
            duration=duration,
            reason=reason,
            expires_at=expires_at,
        )
        session.add(pun)
        await session.commit()
        await session.refresh(pun)
        return pun


async def deactivate_punishment(user_id: int, chat_id: int, ptype: PunishmentType) -> None:
    async with get_session() as session:
        await session.execute(
            update(Punishment)
            .where(
                and_(
                    Punishment.user_id == user_id,
                    Punishment.chat_id == chat_id,
                    Punishment.type == ptype,
                    Punishment.active.is_(True),
                )
            )
            .values(active=False)
        )
        await session.commit()


async def get_active_punishment(user_id: int, chat_id: int, ptype: PunishmentType) -> Optional[Punishment]:
    async with get_session() as session:
        result = await session.execute(
            select(Punishment).where(
                and_(
                    Punishment.user_id == user_id,
                    Punishment.chat_id == chat_id,
                    Punishment.type == ptype,
                    Punishment.active.is_(True),
                )
            )
        )
        return result.scalar_one_or_none()


async def get_balance(user_id: int) -> float:
    async with get_session() as session:
        result = await session.execute(select(User.balance).where(User.id == user_id))
        return result.scalar() or 0.0


async def add_balance(user_id: int, amount: float) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(
                balance=User.balance + amount
            )
        )
        await session.commit()


async def deduct_balance(user_id: int, amount: float) -> bool:
    async with get_session() as session:
        result = await session.execute(select(User.balance).where(User.id == user_id))
        current = result.scalar() or 0.0
        if current < amount:
            return False
        await session.execute(
            update(User).where(User.id == user_id).values(
                balance=User.balance - amount
            )
        )
        await session.commit()
        return True


async def get_chats_with_prices() -> list[Chat]:
    async with get_session() as session:
        result = await session.execute(
            select(Chat).where(Chat.ad_price > 0).order_by(Chat.ad_price.asc())
        )
        return list(result.scalars().all())


async def create_advertisement(
    user_id: int,
    chat_id: int,
    text: str,
    price: float,
    media: str = None,
    media_type: str = None,
    max_posts: int = 1,
) -> Advertisement:
    async with get_session() as session:
        ad = Advertisement(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            media=media,
            media_type=media_type,
            price=price,
            max_posts=max_posts,
        )
        session.add(ad)
        await session.commit()
        await session.refresh(ad)
        return ad


async def get_user_ads(user_id: int) -> list[Advertisement]:
    async with get_session() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.user_id == user_id).order_by(Advertisement.created_at.desc())
        )
        return list(result.scalars().all())


async def get_pending_ads() -> list[Advertisement]:
    async with get_session() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.status == AdStatus.PENDING)
        )
        return list(result.scalars().all())


async def update_ad_status(ad_id: int, status: AdStatus) -> None:
    async with get_session() as session:
        await session.execute(
            update(Advertisement).where(Advertisement.id == ad_id).values(status=status)
        )
        await session.commit()


async def get_ready_ads() -> list[Advertisement]:
    async with get_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Advertisement).where(
                and_(
                    Advertisement.status == AdStatus.APPROVED,
                    Advertisement.times_posted < Advertisement.max_posts,
                    Advertisement.expire_at.is_(None) | (Advertisement.expire_at > now),
                )
            )
        )
        return list(result.scalars().all())


# ─── Role Management ─────────────────────────────────────────

async def get_users_by_role(role: UserRole) -> list[User]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.role == role).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())


async def get_all_admins() -> list[User]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(
                User.role.in_([UserRole.ADMIN, UserRole.SUPERADMIN])
            ).order_by(User.role, User.created_at.desc())
        )
        return list(result.scalars().all())


async def add_group_moderator(
    user_id: int, chat_id: int, created_by: int,
    can_mute: bool = True, can_ban: bool = True,
    can_warn: bool = True, can_kick: bool = True,
    can_delete: bool = True,
) -> GroupModerator:
    async with get_session() as session:
        result = await session.execute(
            select(GroupModerator).where(
                and_(GroupModerator.user_id == user_id, GroupModerator.chat_id == chat_id)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        gm = GroupModerator(
            user_id=user_id, chat_id=chat_id, created_by=created_by,
            can_mute=can_mute, can_ban=can_ban, can_warn=can_warn,
            can_kick=can_kick, can_delete=can_delete,
        )
        session.add(gm)
        await session.commit()
        await session.refresh(gm)
        return gm


async def remove_group_moderator(user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(GroupModerator).where(
                and_(GroupModerator.user_id == user_id, GroupModerator.chat_id == chat_id)
            )
        )
        gm = result.scalar_one_or_none()
        if gm:
            await session.delete(gm)
            await session.commit()
            return True
        return False


async def get_group_moderators(chat_id: int) -> list[GroupModerator]:
    async with get_session() as session:
        result = await session.execute(
            select(GroupModerator).where(GroupModerator.chat_id == chat_id)
        )
        return list(result.scalars().all())


async def is_group_moderator(user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(GroupModerator).where(
                and_(GroupModerator.user_id == user_id, GroupModerator.chat_id == chat_id)
            )
        )
        return result.scalar_one_or_none() is not None


async def is_chat_admin(user_id: int, chat_id: int) -> bool:
    user = await get_user(user_id)
    if user and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        return True
    if await is_group_moderator(user_id, chat_id):
        return True
    return await is_chat_admin_assigned(user_id, chat_id)


async def is_chat_admin_assigned(user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(ChatAdmin).where(
                and_(ChatAdmin.user_id == user_id, ChatAdmin.chat_id == chat_id)
            )
        )
        return result.scalar_one_or_none() is not None


async def add_chat_admin(user_id: int, chat_id: int, added_by: int = 0) -> ChatAdmin:
    async with get_session() as session:
        result = await session.execute(
            select(ChatAdmin).where(
                and_(ChatAdmin.user_id == user_id, ChatAdmin.chat_id == chat_id)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        ca = ChatAdmin(user_id=user_id, chat_id=chat_id, added_by=added_by)
        session.add(ca)
        await session.commit()
        await session.refresh(ca)
        return ca


async def remove_chat_admin(user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(ChatAdmin).where(
                and_(ChatAdmin.user_id == user_id, ChatAdmin.chat_id == chat_id)
            )
        )
        ca = result.scalar_one_or_none()
        if ca:
            await session.delete(ca)
            await session.commit()
            return True
        return False


async def get_chat_admins(chat_id: int) -> list[ChatAdmin]:
    async with get_session() as session:
        result = await session.execute(
            select(ChatAdmin).where(ChatAdmin.chat_id == chat_id)
        )
        return list(result.scalars().all())


async def get_user_chat_ids(user_id: int) -> list[int]:
    async with get_session() as session:
        result = await session.execute(
            select(ChatAdmin.chat_id).where(ChatAdmin.user_id == user_id)
        )
        return [row[0] for row in result.all()]


async def get_all_chat_admins() -> list[ChatAdmin]:
    async with get_session() as session:
        result = await session.execute(
            select(ChatAdmin).order_by(ChatAdmin.chat_id)
        )
        return list(result.scalars().all())


# ─── Reports ─────────────────────────────────────────────────

async def create_report(
    chat_id: int, reporter_id: int, target_id: int,
    message_id: int = None, message_text: str = None, reason: str = None,
) -> Report:
    async with get_session() as session:
        report = Report(
            chat_id=chat_id, reporter_id=reporter_id, target_id=target_id,
            message_id=message_id, message_text=message_text, reason=reason,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report


async def get_pending_reports(chat_id: int = None) -> list[Report]:
    async with get_session() as session:
        q = select(Report).where(Report.status == ReportStatus.PENDING)
        if chat_id:
            q = q.where(Report.chat_id == chat_id)
        q = q.order_by(Report.created_at.desc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def resolve_report(report_id: int, admin_id: int, status: ReportStatus) -> None:
    async with get_session() as session:
        await session.execute(
            update(Report).where(Report.id == report_id).values(
                status=status, resolved_by=admin_id,
            )
        )
        await session.commit()


async def get_report(report_id: int) -> Optional[Report]:
    async with get_session() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        return result.scalar_one_or_none()


# ─── Word Triggers ──────────────────────────────────────────

async def add_word_trigger(
    chat_id: int, word: str, action: TriggerAction,
    mute_duration: int = None, case_sensitive: bool = False, created_by: int = 0,
) -> WordTrigger:
    async with get_session() as session:
        wt = WordTrigger(
            chat_id=chat_id, word=word, action=action,
            mute_duration=mute_duration, case_sensitive=case_sensitive,
            created_by=created_by,
        )
        session.add(wt)
        await session.commit()
        await session.refresh(wt)
        return wt


async def remove_word_trigger(trigger_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(select(WordTrigger).where(WordTrigger.id == trigger_id))
        wt = result.scalar_one_or_none()
        if wt:
            await session.delete(wt)
            await session.commit()
            return True
        return False


async def get_word_triggers(chat_id: int) -> list[WordTrigger]:
    async with get_session() as session:
        result = await session.execute(
            select(WordTrigger).where(WordTrigger.chat_id == chat_id)
        )
        return list(result.scalars().all())


# ─── Message Count ──────────────────────────────────────────

async def increment_message_count(user_id: int, chat_id: int) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(MessageCount).where(
                and_(MessageCount.user_id == user_id, MessageCount.chat_id == chat_id)
            )
        )
        mc = result.scalar_one_or_none()
        if mc:
            mc.count += 1
        else:
            mc = MessageCount(user_id=user_id, chat_id=chat_id, count=1)
            session.add(mc)
        await session.commit()


async def get_message_stats(user_id: int, chat_id: int = None) -> list[MessageCount] | int:
    async with get_session() as session:
        if chat_id:
            result = await session.execute(
                select(MessageCount).where(
                    and_(MessageCount.user_id == user_id, MessageCount.chat_id == chat_id)
                )
            )
            mc = result.scalar_one_or_none()
            return mc.count if mc else 0
        result = await session.execute(
            select(MessageCount).where(MessageCount.user_id == user_id)
        )
        return list(result.scalars().all())


async def get_top_users(chat_id: int, limit: int = 10) -> list[MessageCount]:
    async with get_session() as session:
        result = await session.execute(
            select(MessageCount).where(MessageCount.chat_id == chat_id)
            .order_by(MessageCount.count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# ─── Scheduled Messages ────────────────────────────────────

async def create_scheduled_message(
    chat_id: int, text: str, send_at: datetime, created_by: int,
    media: str = None, media_type: str = None,
) -> ScheduledMessage:
    async with get_session() as session:
        sm = ScheduledMessage(
            chat_id=chat_id, text=text, send_at=send_at,
            created_by=created_by, media=media, media_type=media_type,
        )
        session.add(sm)
        await session.commit()
        await session.refresh(sm)
        return sm


async def get_pending_scheduled() -> list[ScheduledMessage]:
    async with get_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(ScheduledMessage).where(
                and_(
                    ScheduledMessage.status == ScheduledStatus.PENDING,
                    ScheduledMessage.send_at <= now,
                )
            )
        )
        return list(result.scalars().all())


async def mark_scheduled_sent(msg_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(ScheduledMessage).where(ScheduledMessage.id == msg_id)
            .values(status=ScheduledStatus.SENT)
        )
        await session.commit()


async def get_user_scheduled(user_id: int) -> list[ScheduledMessage]:
    async with get_session() as session:
        result = await session.execute(
            select(ScheduledMessage).where(
                and_(
                    ScheduledMessage.created_by == user_id,
                    ScheduledMessage.status == ScheduledStatus.PENDING,
                )
            )
        )
        return list(result.scalars().all())


async def cancel_scheduled(msg_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(ScheduledMessage).where(ScheduledMessage.id == msg_id)
        )
        sm = result.scalar_one_or_none()
        if sm and sm.status == ScheduledStatus.PENDING:
            sm.status = ScheduledStatus.CANCELLED
            await session.commit()
            return True
        return False


# ─── Chat helpers ──────────────────────────────────────────

async def update_chat(chat_id: int, **kwargs) -> None:
    async with get_session() as session:
        await session.execute(
            update(Chat).where(Chat.id == chat_id).values(**kwargs)
        )
        await session.commit()


# ─── Recurring Posts ────────────────────────────────────────

async def create_recurring_post(
    chat_id: int, text: str, hour: int, minute: int = 0,
    day_of_week: int = None, interval_days: int = None,
    media: str = None, media_type: str = None, created_by: int = 0,
) -> RecurringPost:
    async with get_session() as session:
        rp = RecurringPost(
            chat_id=chat_id, text=text, hour=hour, minute=minute,
            day_of_week=day_of_week, interval_days=interval_days,
            media=media, media_type=media_type, created_by=created_by,
        )
        session.add(rp)
        await session.commit()
        await session.refresh(rp)
        return rp


async def get_recurring_posts(chat_id: int = None) -> list[RecurringPost]:
    async with get_session() as session:
        q = select(RecurringPost).where(RecurringPost.is_active.is_(True))
        if chat_id:
            q = q.where(RecurringPost.chat_id == chat_id)
        result = await session.execute(q)
        return list(result.scalars().all())


async def delete_recurring_post(post_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(select(RecurringPost).where(RecurringPost.id == post_id))
        rp = result.scalar_one_or_none()
        if rp:
            rp.is_active = False
            await session.commit()
            return True
        return False


# ─── RSS Feeds ──────────────────────────────────────────────

async def create_rss_feed(
    chat_id: int, url: str, title: str = None,
    interval_minutes: int = 15, created_by: int = 0,
) -> RssFeed:
    async with get_session() as session:
        rf = RssFeed(
            chat_id=chat_id, url=url, title=title,
            interval_minutes=interval_minutes, created_by=created_by,
        )
        session.add(rf)
        await session.commit()
        await session.refresh(rf)
        return rf


async def get_active_rss_feeds() -> list[RssFeed]:
    async with get_session() as session:
        result = await session.execute(
            select(RssFeed).where(RssFeed.is_active.is_(True))
        )
        return list(result.scalars().all())


async def get_chat_rss_feeds(chat_id: int) -> list[RssFeed]:
    async with get_session() as session:
        result = await session.execute(
            select(RssFeed).where(
                and_(RssFeed.chat_id == chat_id, RssFeed.is_active.is_(True))
            )
        )
        return list(result.scalars().all())


async def remove_rss_feed(feed_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(select(RssFeed).where(RssFeed.id == feed_id))
        rf = result.scalar_one_or_none()
        if rf:
            rf.is_active = False
            await session.commit()
            return True
        return False


async def update_rss_feed(feed_id: int, **kwargs) -> None:
    async with get_session() as session:
        await session.execute(
            update(RssFeed).where(RssFeed.id == feed_id).values(**kwargs)
        )
        await session.commit()


# ─── Payments ───────────────────────────────────────────────

async def create_payment(user_id: int, stars_amount: int, rub_amount: float) -> Payment:
    async with get_session() as session:
        p = Payment(user_id=user_id, stars_amount=stars_amount, rub_amount=rub_amount)
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p


async def confirm_and_topup(user_id: int, rub_amount: float, charge_id: str, stars_amount: int) -> None:
    async with get_session() as session:
        p = Payment(
            user_id=user_id, telegram_payment_charge_id=charge_id,
            stars_amount=stars_amount, rub_amount=rub_amount, status="confirmed",
        )
        session.add(p)
        await session.execute(
            update(User).where(User.id == user_id).values(
                balance=User.balance + rub_amount
            )
        )
        await session.commit()


async def get_user_payments(user_id: int) -> list[Payment]:
    async with get_session() as session:
        result = await session.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
        )
        return list(result.scalars().all())


# ─── Auto Delete ────────────────────────────────────────────

async def schedule_auto_delete(chat_id: int, message_id: int, delete_at: datetime) -> AutoDeleteMessage:
    async with get_session() as session:
        adm = AutoDeleteMessage(chat_id=chat_id, message_id=message_id, delete_at=delete_at)
        session.add(adm)
        await session.commit()
        return adm


async def get_expired_messages() -> list[AutoDeleteMessage]:
    async with get_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(AutoDeleteMessage).where(AutoDeleteMessage.delete_at <= now)
        )
        return list(result.scalars().all())


async def delete_auto_message_record(msg_id: int) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(AutoDeleteMessage).where(AutoDeleteMessage.id == msg_id)
        )
        adm = result.scalar_one_or_none()
        if adm:
            await session.delete(adm)
            await session.commit()


# ─── Giveaways ─────────────────────────────────────────────

async def create_giveaway(
    chat_id: int, creator_id: int, title: str, prize: str,
    ends_at: datetime, winners_count: int = 1, description: str = None,
    require_channels: str = None, require_repost: bool = False,
    repost_channel_id: int = None, repost_message_id: int = None,
) -> Giveaway:
    async with get_session() as session:
        g = Giveaway(
            chat_id=chat_id, creator_id=creator_id,
            title=title, prize=prize, description=description,
            winners_count=winners_count, ends_at=ends_at,
            require_channels=require_channels, require_repost=require_repost,
            repost_channel_id=repost_channel_id, repost_message_id=repost_message_id,
        )
        session.add(g)
        await session.commit()
        await session.refresh(g)
        return g


async def update_giveaway_message(giveaway_id: int, message_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(Giveaway).where(Giveaway.id == giveaway_id).values(message_id=message_id)
        )
        await session.commit()


async def get_active_giveaways(chat_id: int = None) -> list[Giveaway]:
    async with get_session() as session:
        q = select(Giveaway).where(Giveaway.status == "active")
        if chat_id:
            q = q.where(Giveaway.chat_id == chat_id)
        q = q.order_by(Giveaway.created_at.desc())
        result = await session.execute(q)
        return list(result.scalars().all())


async def get_expired_giveaways() -> list[Giveaway]:
    async with get_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Giveaway).where(
                Giveaway.status == "active",
                Giveaway.ends_at <= now,
            )
        )
        return list(result.scalars().all())


async def complete_giveaway(giveaway_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(Giveaway).where(Giveaway.id == giveaway_id).values(status="completed")
        )
        await session.commit()


async def cancel_giveaway(giveaway_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(Giveaway).where(Giveaway.id == giveaway_id).values(status="cancelled")
        )
        await session.commit()


async def add_giveaway_participant(giveaway_id: int, user_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(GiveawayParticipant).where(
                and_(
                    GiveawayParticipant.giveaway_id == giveaway_id,
                    GiveawayParticipant.user_id == user_id,
                )
            )
        )
        if result.scalar_one_or_none():
            return False
        gp = GiveawayParticipant(giveaway_id=giveaway_id, user_id=user_id)
        session.add(gp)
        await session.commit()
        return True


async def get_giveaway_participants(giveaway_id: int) -> list[GiveawayParticipant]:
    async with get_session() as session:
        result = await session.execute(
            select(GiveawayParticipant).where(
                GiveawayParticipant.giveaway_id == giveaway_id
            )
        )
        return list(result.scalars().all())


async def get_giveaway(giveaway_id: int) -> Optional[Giveaway]:
    async with get_session() as session:
        result = await session.execute(
            select(Giveaway).where(Giveaway.id == giveaway_id)
        )
        return result.scalar_one_or_none()


async def set_participant_repost_verified(giveaway_id: int, user_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(GiveawayParticipant)
            .where(
                and_(
                    GiveawayParticipant.giveaway_id == giveaway_id,
                    GiveawayParticipant.user_id == user_id,
                )
            )
            .values(repost_verified=True)
        )
        await session.commit()
