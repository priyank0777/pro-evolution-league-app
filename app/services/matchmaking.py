from typing import Dict, List, Optional, Tuple
import networkx as nx
from sqlalchemy.orm import Session

from app.models import Match, Preference, Team, User


def build_complete_preference_matrix(
    users: List[User], preferences: List[Preference]
) -> Tuple[Dict[int, List[int]], Dict[Tuple[int, int], int]]:
    """
    Build complete strict preference lists and rank lookup for all eligible players.
    If a user has not submitted full rankings, unranked peers are appended in
    deterministic order by user ID with default bottom ranks.
    """
    user_ids = sorted([u.id for u in users])
    pref_map: Dict[int, List[Tuple[int, int]]] = {uid: [] for uid in user_ids}

    for p in preferences:
        if p.user_id in pref_map and p.ranked_user_id in pref_map and p.user_id != p.ranked_user_id:
            pref_map[p.user_id].append((p.rank_value, p.ranked_user_id))

    ordered_lists: Dict[int, List[int]] = {}
    rank_lookup: Dict[Tuple[int, int], int] = {}

    for uid in user_ids:
        submitted = sorted(pref_map[uid], key=lambda item: (item[0], item[1]))
        ranked_peers = []
        seen = set()
        for _, peer_id in submitted:
            if peer_id not in seen:
                ranked_peers.append(peer_id)
                seen.add(peer_id)

        # Append any unranked peers deterministically
        for peer_id in user_ids:
            if peer_id != uid and peer_id not in seen:
                ranked_peers.append(peer_id)
                seen.add(peer_id)

        ordered_lists[uid] = ranked_peers
        for idx, peer_id in enumerate(ranked_peers, start=1):
            rank_lookup[(uid, peer_id)] = idx

    return ordered_lists, rank_lookup


def _irving_stable_roommates(
    ordered_lists: Dict[int, List[int]],
) -> Optional[List[Tuple[int, int]]]:
    """
    Attempt Irving's (1985) Stable Roommates Algorithm (Phase 1 + Phase 2).
    Returns a list of stable pairs if a strict stable matching exists, else None.
    """
    prefs: Dict[int, List[int]] = {u: list(lst) for u, lst in ordered_lists.items()}
    proposals: Dict[int, Optional[int]] = {u: None for u in prefs}
    held_by: Dict[int, Optional[int]] = {u: None for u in prefs}

    # Phase 1: Proposal and symmetrical reduction
    unmatched = list(prefs.keys())
    while unmatched:
        proposer = unmatched[0]
        if not prefs[proposer]:
            return None

        target = prefs[proposer][0]
        current_holder = held_by[target]

        if current_holder is not None:
            # Target compares proposer vs current_holder
            if prefs[target].index(proposer) < prefs[target].index(current_holder):
                # Reject current_holder
                proposals[current_holder] = None
                if target in prefs[current_holder]:
                    prefs[current_holder].remove(target)
                if current_holder in prefs[target]:
                    prefs[target].remove(current_holder)
                unmatched.append(current_holder)
            else:
                # Reject proposer
                prefs[proposer].remove(target)
                if proposer in prefs[target]:
                    prefs[target].remove(proposer)
                continue

        # Target holds proposer's proposal
        held_by[target] = proposer
        proposals[proposer] = target
        unmatched.remove(proposer)

        # Symmetrically remove worse options than proposer from target's list
        cutoff = prefs[target].index(proposer)
        to_remove = prefs[target][cutoff + 1 :]
        for worse in to_remove:
            prefs[target].remove(worse)
            if target in prefs[worse]:
                prefs[worse].remove(target)

    # Verify non-empty reduced lists
    for u, lst in prefs.items():
        if not lst:
            return None

    # Phase 2: All-or-nothing cycle elimination until every list has length 1
    max_iterations = len(prefs) * len(prefs)
    iterations = 0
    while any(len(lst) > 1 for lst in prefs.values()):
        iterations += 1
        if iterations > max_iterations:
            return None

        # Find a participant with > 1 elements in reduced preference list
        start = next((u for u, lst in prefs.items() if len(lst) > 1), None)
        if start is None:
            break

        p_seq = [start]
        q_seq = []
        visited = {start: 0}

        while True:
            curr_p = p_seq[-1]
            if len(prefs[curr_p]) < 2:
                return None
            next_q = prefs[curr_p][1]  # Second preference
            q_seq.append(next_q)
            next_p = prefs[next_q][-1]  # Last preference of next_q
            if next_p in visited:
                cycle_start = visited[next_p]
                p_cycle = p_seq[cycle_start:]
                q_cycle = q_seq[cycle_start:]
                break
            visited[next_p] = len(p_seq)
            p_seq.append(next_p)

        # Eliminate rotation
        for i in range(len(q_cycle)):
            q_i = q_cycle[i]
            p_next = p_cycle[(i + 1) % len(p_cycle)]
            # Reject p_next's proposal held by q_i
            if p_next in prefs[q_i]:
                prefs[q_i].remove(p_next)
            if q_i in prefs[p_next]:
                prefs[p_next].remove(q_i)
            if not prefs[q_i] or not prefs[p_next]:
                return None

            # q_i now holds proposal from p_cycle[i]; prune worse than p_cycle[i]
            p_i = p_cycle[i]
            if p_i not in prefs[q_i]:
                return None
            cutoff = prefs[q_i].index(p_i)
            for worse in list(prefs[q_i][cutoff + 1 :]):
                prefs[q_i].remove(worse)
                if q_i in prefs[worse]:
                    prefs[worse].remove(q_i)

    # Extract pairs and confirm symmetry
    pairs = []
    paired = set()
    for u, lst in prefs.items():
        if len(lst) != 1:
            return None
        v = lst[0]
        if prefs[v] != [u]:
            return None
        if u not in paired and v not in paired:
            pairs.append((min(u, v), max(u, v)))
            paired.add(u)
            paired.add(v)

    if len(pairs) * 2 != len(prefs):
        return None
    return sorted(pairs)


def _minimum_weight_matching(
    user_ids: List[int], rank_lookup: Dict[Tuple[int, int], int]
) -> List[Tuple[int, int]]:
    """
    Compute a global Minimum-Weight Perfect Matching using NetworkX's Blossom algorithm.
    Minimizes mutual rank sum: cost(u, v) = rank(u -> v) + rank(v -> u),
    with a slight tie-breaker penalty |rank(u->v) - rank(v->u)| to favor balanced mutual choices.
    """
    n = len(user_ids)
    max_possible_cost = 4 * n * n + 1000
    graph = nx.Graph()

    for i in range(n):
        for j in range(i + 1, n):
            u, v = user_ids[i], user_ids[j]
            r_uv = rank_lookup[(u, v)]
            r_vu = rank_lookup[(v, u)]
            # Primary cost: sum of mutual ranks (scaled by 100), secondary: absolute rank diff
            mutual_cost = (r_uv + r_vu) * 100 + abs(r_uv - r_vu)
            weight = max_possible_cost - mutual_cost
            graph.add_edge(u, v, weight=weight)

    matching = nx.max_weight_matching(graph, maxcardinality=True)
    pairs = [(min(u, v), max(u, v)) for u, v in matching]
    return sorted(pairs)


def run_partner_matchmaking(db: Session) -> Tuple[List[Team], str]:
    """
    Pair all non-admin players into 2v2 teams based on their preference rankings.
    First tries Irving's Stable Roommates algorithm; if the preference instance has
    an odd-rotation cycle (no strict theoretical stable partition), seamlessly falls
    back to Minimum-Weight Maximum-Cardinality Blossom Matching.
    """
    players = (
        db.query(User)
        .filter(User.is_admin == False)  # noqa: E712
        .order_by(User.id.asc())
        .all()
    )

    if len(players) < 4:
        raise ValueError(
            f"At least 4 non-admin players are required to form a league (currently {len(players)})."
        )
    if len(players) % 2 != 0:
        raise ValueError(
            f"An even number of non-admin players is required for 2v2 matchmaking (currently {len(players)}). "
            "Please add or remove 1 player in User Management."
        )

    all_prefs = db.query(Preference).all()
    ordered_lists, rank_lookup = build_complete_preference_matrix(players, all_prefs)

    # Attempt Irving's Stable Roommates first, fallback to Blossom Minimum-Weight Matching
    pairs = _irving_stable_roommates(ordered_lists)
    algorithm_used = "Irving Stable Roommates"
    if pairs is None:
        user_ids = [p.id for p in players]
        pairs = _minimum_weight_matching(user_ids, rank_lookup)
        algorithm_used = "Minimum-Weight Mutual Rank Blossom Matching"

    # Clear existing matches and teams before creating the newly matched teams
    db.query(Match).delete()
    db.query(Team).delete()
    db.flush()

    user_by_id = {u.id: u for u in players}
    created_teams: List[Team] = []

    for idx, (u_id, v_id) in enumerate(pairs, start=1):
        u_player = user_by_id[u_id]
        v_player = user_by_id[v_id]
        default_name = f"Team {idx}: {u_player.name.split()[0]} & {v_player.name.split()[0]}"
        # Ensure uniqueness
        team = Team(
            name=f"{default_name} (#{idx})",
            leader_id=u_id,
            player1_id=u_id,
            player2_id=v_id,
        )
        db.add(team)
        created_teams.append(team)

    db.commit()
    for t in created_teams:
        db.refresh(t)

    return created_teams, algorithm_used

