from datetime import datetime
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import MatchStatus


# ---------------------------------------------------------------------------
# Auth & User Schemas
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    efootball_username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)


class UserLogin(BaseModel):
    efootball_username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    efootball_username: str
    is_admin: bool
    created_at: datetime
    team_id: Optional[int] = None
    team_name: Optional[str] = None


class UserPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    efootball_username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Preference Schemas
# ---------------------------------------------------------------------------
class PreferenceItemIn(BaseModel):
    ranked_user_id: int
    rank_value: int = Field(..., ge=1)


class PreferenceListIn(BaseModel):
    rankings: List[PreferenceItemIn]


class PreferenceOut(BaseModel):
    ranked_user_id: int
    rank_value: int
    name: str
    efootball_username: str


# ---------------------------------------------------------------------------
# Team Schemas
# ---------------------------------------------------------------------------
class TeamUpdateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    leader_id: int


class TeamOut(BaseModel):
    id: int
    name: str
    leader_id: Optional[int]
    leader_name: Optional[str]
    player1: UserPublicOut
    player2: UserPublicOut


# ---------------------------------------------------------------------------
# Match & MatchStat Schemas
# ---------------------------------------------------------------------------
class PlayerStatIn(BaseModel):
    user_id: int
    total_points: int = Field(default=0, ge=0)
    goals: int = Field(default=0, ge=0)
    assists: int = Field(default=0, ge=0)


class PlayerStatOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    efootball_username: str
    team_id: Optional[int] = None
    total_points: int
    goals: int
    assists: int


class MatchSubmitIn(BaseModel):
    home_score: int = Field(..., ge=0)
    away_score: int = Field(..., ge=0)
    player_stats: List[PlayerStatIn] = Field(default_factory=list)


class MatchVerifyIn(BaseModel):
    action: str = Field(..., pattern="^(accept|dispute)$")


class AdminMatchOverrideIn(BaseModel):
    home_score: int = Field(..., ge=0)
    away_score: int = Field(..., ge=0)
    status: MatchStatus = MatchStatus.ACCEPTED
    player_stats: List[PlayerStatIn] = Field(default_factory=list)


class MatchOut(BaseModel):
    id: int
    matchweek: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_score: Optional[int]
    away_score: Optional[int]
    status: MatchStatus
    deadline: Optional[datetime]
    submitted_at: Optional[datetime]
    verified_at: Optional[datetime]
    home_players: List[UserPublicOut]
    away_players: List[UserPublicOut]
    player_stats: List[PlayerStatOut]


# ---------------------------------------------------------------------------
# Standings & Leaderboard Schemas
# ---------------------------------------------------------------------------
class StandingRowOut(BaseModel):
    position: int
    team_id: int
    team_name: str
    leader_name: Optional[str]
    members: List[str]
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class PlayerLeaderboardRowOut(BaseModel):
    rank: int
    user_id: int
    name: str
    efootball_username: str
    team_name: Optional[str]
    matches_played: int
    total_points: int
    goals: int
    assists: int
    avg_points: float


# ---------------------------------------------------------------------------
# System Settings & Admin Action Schemas
# ---------------------------------------------------------------------------
class SystemSettingsOut(BaseModel):
    registration_open: bool
    preferences_open: bool
    team_setup_open: bool
    season_live: bool
    round_robin_multiplier: int
    matches_per_week: int
    current_matchweek: int
    week_end_day: int
    week_end_time_ist: str
    track_points: bool
    track_goals: bool
    track_assists: bool


class SystemSettingsUpdateIn(BaseModel):
    registration_open: Optional[bool] = None
    preferences_open: Optional[bool] = None
    team_setup_open: Optional[bool] = None
    season_live: Optional[bool] = None
    round_robin_multiplier: Optional[int] = Field(default=None, ge=1, le=10)
    matches_per_week: Optional[int] = Field(default=None, ge=1, le=10)
    current_matchweek: Optional[int] = Field(default=None, ge=1)
    week_end_day: Optional[int] = Field(default=None, ge=0, le=6)
    week_end_time_ist: Optional[str] = None
    track_points: Optional[bool] = None
    track_goals: Optional[bool] = None
    track_assists: Optional[bool] = None

    @field_validator("week_end_time_ist")
    @classmethod
    def validate_ist_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?", v.strip())
        if not m:
            raise ValueError("week_end_time_ist must be in HH:MM or HH:MM:SS (24-hour) format.")
        hh, mm, ss = m.group(1), m.group(2), m.group(3) or "00"
        return f"{hh}:{mm}:{ss}"


class GenerateFixturesIn(BaseModel):
    round_robin_multiplier: Optional[int] = Field(default=None, ge=1, le=10)
    matches_per_week: Optional[int] = Field(default=None, ge=1, le=10)
    start_friday_iso: Optional[str] = None

