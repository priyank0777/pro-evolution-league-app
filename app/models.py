import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MatchStatus(str, enum.Enum):
    """Lifecycle states of a scheduled league match."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    AUTO_DRAWN = "auto_drawn"


class User(Base):
    """Registered player or administrator account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    efootball_username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    preferences_given = relationship(
        "Preference",
        foreign_keys="Preference.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preferences_received = relationship(
        "Preference",
        foreign_keys="Preference.ranked_user_id",
        back_populates="ranked_user",
        cascade="all, delete-orphan",
    )
    match_stats = relationship(
        "MatchStat",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Preference(Base):
    """Partner preference ranking submitted during the Preference Phase."""

    __tablename__ = "preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "ranked_user_id", name="uq_user_ranked_target"),
        UniqueConstraint("user_id", "rank_value", name="uq_user_rank_position"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ranked_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank_value = Column(Integer, nullable=False)  # 1 = most preferred partner

    user = relationship(
        "User", foreign_keys=[user_id], back_populates="preferences_given"
    )
    ranked_user = relationship(
        "User", foreign_keys=[ranked_user_id], back_populates="preferences_received"
    )


class Team(Base):
    """2v2 paired team generated via matchmaking."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False)
    leader_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    player1_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    player2_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    leader = relationship("User", foreign_keys=[leader_id])
    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])

    home_matches = relationship(
        "Match",
        foreign_keys="Match.home_team_id",
        back_populates="home_team",
        cascade="all, delete-orphan",
    )
    away_matches = relationship(
        "Match",
        foreign_keys="Match.away_team_id",
        back_populates="away_team",
        cascade="all, delete-orphan",
    )


class Match(Base):
    """Scheduled fixture between two 2v2 teams in a specific matchweek."""

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    matchweek = Column(Integer, nullable=False, index=True)
    home_team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    away_team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    status = Column(
        Enum(MatchStatus, native_enum=False),
        default=MatchStatus.PENDING,
        nullable=False,
        index=True,
    )
    deadline = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    home_team = relationship(
        "Team", foreign_keys=[home_team_id], back_populates="home_matches"
    )
    away_team = relationship(
        "Team", foreign_keys=[away_team_id], back_populates="away_matches"
    )
    player_stats = relationship(
        "MatchStat",
        back_populates="match",
        cascade="all, delete-orphan",
    )


class MatchStat(Base):
    """Individual human player statistics for a single match."""

    __tablename__ = "match_stats"
    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_match_user_stat"),
    )

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_points = Column(Integer, default=0, nullable=False)
    goals = Column(Integer, default=0, nullable=False)
    assists = Column(Integer, default=0, nullable=False)

    match = relationship("Match", back_populates="player_stats")
    user = relationship("User", back_populates="match_stats")


class SystemSetting(Base):
    """Global key-value configuration for tournament state machine & stat toggles."""

    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(String(255), nullable=False)

