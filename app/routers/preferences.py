from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_system_settings_model
from app.database import get_db
from app.models import Preference, User
from app.schemas import PreferenceListIn, PreferenceOut

router = APIRouter(prefix="/api/preferences", tags=["Preferences"])


@router.get("", response_model=List[PreferenceOut])
def get_my_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the ordered list of all other non-admin registered players for the
    authenticated user. If the user has already saved rankings, those ranks are
    preserved; any newly registered users are appended at the bottom.
    """
    other_players = (
        db.query(User)
        .filter(User.is_admin == False, User.id != current_user.id)  # noqa: E712
        .order_by(User.id.asc())
        .all()
    )

    existing_prefs = (
        db.query(Preference)
        .filter(Preference.user_id == current_user.id)
        .order_by(Preference.rank_value.asc())
        .all()
    )
    rank_map = {p.ranked_user_id: p.rank_value for p in existing_prefs}

    ranked_players = [p for p in other_players if p.id in rank_map]
    ranked_players.sort(key=lambda u: rank_map[u.id])
    unranked_players = [p for p in other_players if p.id not in rank_map]

    combined = ranked_players + unranked_players
    return [
        PreferenceOut(
            ranked_user_id=player.id,
            rank_value=idx,
            name=player.name,
            efootball_username=player.efootball_username,
        )
        for idx, player in enumerate(combined, start=1)
    ]


@router.put("", response_model=List[PreferenceOut])
def update_my_preferences(
    payload: PreferenceListIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save or update the authenticated player's partner preference rankings.
    Editable only while the Preference Phase toggle is enabled by the Admin.
    """
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin accounts do not participate in partner preference rankings.",
        )

    sys_settings = get_system_settings_model(db)
    if not sys_settings.preferences_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Preference Phase is currently closed by the Administrator.",
        )

    eligible_peers = (
        db.query(User)
        .filter(User.is_admin == False, User.id != current_user.id)  # noqa: E712
        .all()
    )
    eligible_ids = {u.id for u in eligible_peers}

    submitted_ids = [item.ranked_user_id for item in payload.rankings]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate users found in preference ranking list.",
        )
    if set(submitted_ids) != eligible_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must rank all other registered non-admin players.",
        )

    # Sort by submitted rank_value and normalize ranks 1..N
    sorted_items = sorted(payload.rankings, key=lambda x: x.rank_value)

    db.query(Preference).filter(Preference.user_id == current_user.id).delete()
    db.flush()

    for normalized_rank, item in enumerate(sorted_items, start=1):
        db.add(
            Preference(
                user_id=current_user.id,
                ranked_user_id=item.ranked_user_id,
                rank_value=normalized_rank,
            )
        )

    db.commit()
    return get_my_preferences(current_user=current_user, db=db)

