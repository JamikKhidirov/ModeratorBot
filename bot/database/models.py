from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, DateTime, Text, Float, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
import enum

from bot.database.base import Base


class UserRole(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class PunishmentType(str, enum.Enum):
    WARN = "warn"
    MUTE = "mute"
    BAN = "ban"
    KICK = "kick"


class AdStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class TriggerAction(str, enum.Enum):
    DELETE = "delete"
    MUTE = "mute"
    WARN = "warn"
    BAN = "ban"
    DELETE_WARN = "delete_warn"
    DELETE_MUTE = "delete_mute"


class ScheduledStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.USER)
    balance = Column(Float, default=0.0)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    warnings = relationship("Warning", back_populates="user", cascade="all, delete-orphan")
    ads = relationship("Advertisement", back_populates="user", cascade="all, delete-orphan")
    punishments = relationship("Punishment", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", foreign_keys="Report.reporter_id", back_populates="reporter", cascade="all, delete-orphan")
    stats = relationship("MessageCount", back_populates="user", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    title = Column(String(256), nullable=True)
    type = Column(String(32), nullable=False)
    username = Column(String(64), nullable=True)
    is_moderated = Column(Boolean, default=True)
    welcome_enabled = Column(Boolean, default=False)
    welcome_message = Column(Text, nullable=True)
    captcha_enabled = Column(Boolean, default=False)
    delete_links = Column(Boolean, default=False)
    delete_bad_words = Column(Boolean, default=False)
    delete_media = Column(Boolean, default=False)
    delete_stickers = Column(Boolean, default=False)
    auto_mute_links = Column(Boolean, default=False)
    mute_duration = Column(Integer, default=60)
    anti_raid = Column(Boolean, default=False)
    anti_raid_days = Column(Integer, default=7)
    log_chat_id = Column(BigInteger, nullable=True)
    silent_mode = Column(Boolean, default=False)
    ad_price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    settings = relationship("ChatSettings", back_populates="chat", uselist=False, cascade="all, delete-orphan")
    ads = relationship("Advertisement", back_populates="chat", cascade="all, delete-orphan")


class ChatSettings(Base):
    __tablename__ = "chat_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), unique=True, nullable=False)
    bad_words = Column(Text, nullable=True)
    allowed_links = Column(Text, nullable=True)
    welcome_photo = Column(String(512), nullable=True)
    welcome_buttons = Column(Text, nullable=True)
    max_warns = Column(Integer, default=3)
    auto_delete_time = Column(Integer, default=0)
    slow_mode = Column(Integer, default=0)

    chat = relationship("Chat", back_populates="settings")


class Warning(Base):
    __tablename__ = "warnings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="warnings")


class Punishment(Base):
    __tablename__ = "punishments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    type = Column(SAEnum(PunishmentType), nullable=False)
    duration = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="punishments")


class GroupModerator(Base):
    __tablename__ = "group_moderators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    can_mute = Column(Boolean, default=True)
    can_ban = Column(Boolean, default=True)
    can_warn = Column(Boolean, default=True)
    can_kick = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(BigInteger, nullable=False)


class Advertisement(Base):
    __tablename__ = "advertisements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=False)
    text = Column(Text, nullable=False)
    media = Column(String(512), nullable=True)
    media_type = Column(String(16), nullable=True)
    status = Column(SAEnum(AdStatus), default=AdStatus.PENDING)
    price = Column(Float, nullable=False)
    views_goal = Column(Integer, nullable=True)
    views_current = Column(Integer, default=0)
    schedule_time = Column(DateTime, nullable=True)
    expire_at = Column(DateTime, nullable=True)
    times_posted = Column(Integer, default=0)
    max_posts = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="ads")
    chat = relationship("Chat", back_populates="ads")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    reporter_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    target_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=True)
    message_text = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(ReportStatus), default=ReportStatus.PENDING)
    resolved_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reporter = relationship("User", back_populates="reports")


class WordTrigger(Base):
    __tablename__ = "word_triggers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    word = Column(String(256), nullable=False)
    action = Column(SAEnum(TriggerAction), nullable=False)
    mute_duration = Column(Integer, nullable=True)
    case_sensitive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(BigInteger, nullable=False)


class MessageCount(Base):
    __tablename__ = "message_counts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="stats")


class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    text = Column(Text, nullable=True)
    media = Column(String(512), nullable=True)
    media_type = Column(String(16), nullable=True)
    status = Column(SAEnum(ScheduledStatus), default=ScheduledStatus.PENDING)
    send_at = Column(DateTime, nullable=False)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RecurringPost(Base):
    __tablename__ = "recurring_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    text = Column(Text, nullable=True)
    media = Column(String(512), nullable=True)
    media_type = Column(String(16), nullable=True)
    day_of_week = Column(Integer, nullable=True)
    hour = Column(Integer, nullable=False)
    minute = Column(Integer, default=0)
    interval_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RssFeed(Base):
    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    url = Column(String(1024), nullable=False)
    title = Column(String(256), nullable=True)
    last_fetched = Column(DateTime, nullable=True)
    last_guid = Column(String(512), nullable=True)
    interval_minutes = Column(Integer, default=15)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    telegram_payment_charge_id = Column(String(256), nullable=True)
    stars_amount = Column(Integer, nullable=False)
    rub_amount = Column(Float, nullable=False)
    status = Column(String(32), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AutoDeleteMessage(Base):
    __tablename__ = "auto_delete_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=False)
    delete_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatAdmin(Base):
    __tablename__ = "chat_admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    added_by = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Giveaway(Base):
    __tablename__ = "giveaways"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    creator_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=True)
    title = Column(String(256), nullable=False)
    prize = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    winners_count = Column(Integer, default=1)
    require_channels = Column(Text, nullable=True)
    require_repost = Column(Boolean, default=False)
    repost_channel_id = Column(BigInteger, nullable=True)
    repost_message_id = Column(Integer, nullable=True)
    status = Column(String(32), default="active")
    ends_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GiveawayParticipant(Base):
    __tablename__ = "giveaway_participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    giveaway_id = Column(Integer, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    repost_verified = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
