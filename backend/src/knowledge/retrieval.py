from collections.abc import Sequence

RRF_RANK_CONSTANT = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]],
    *,
    rank_constant: int = RRF_RANK_CONSTANT,
) -> dict[str, float]:
    """Сливает списки кандидатов по Reciprocal Rank Fusion."""
    if rank_constant < 1:
        raise ValueError("Константа RRF должна быть положительной.")

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    seen_counter = 0
    for ranking in rankings:
        seen_in_ranking: set[str] = set()
        rank = 0
        for source_id in ranking:
            if source_id in seen_in_ranking:
                continue
            seen_in_ranking.add(source_id)
            rank += 1
            scores[source_id] = scores.get(source_id, 0.0) + 1 / (rank_constant + rank)
            if source_id not in first_seen:
                first_seen[source_id] = seen_counter
                seen_counter += 1

    return dict(
        sorted(
            scores.items(),
            key=lambda item: (-item[1], first_seen[item[0]]),
        )
    )
