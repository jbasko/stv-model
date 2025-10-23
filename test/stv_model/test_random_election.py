import logging
import random
from typing import Sequence

from stv_model.model import Election, Ballot, CandidateId, Candidate

logger = logging.getLogger(__name__)


def generate_candidates():
    for candidate_id in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        yield Candidate(id=candidate_id)


def generate_random_ballots(
    candidates: Sequence[CandidateId],
    random_strength_factor: float = 1.0,
    random_strength: bool = False,
    num_ballots=1000,
):
    num_candidates = len(candidates)
    for i in range(num_ballots):
        num_selections = random.randint(0, num_candidates)
        prefs = list(random.sample(candidates, num_selections))

        strength = 1.0
        if random_strength:
            strength *= random.randint(1, 10) * random_strength_factor

        yield Ballot(
            id=f"ballot_{i+1}",
            prefs=tuple(prefs),
            strength=strength,
        )


def test_election():
    candidates = {c.id: c for c in generate_candidates()}
    el = Election(
        num_seats=5,
        candidates=candidates,
    )
    for ballot in generate_random_ballots(
        num_ballots=100,
        candidates=list(candidates.keys()),
        random_strength=True,
        random_strength_factor=10.0,
    ):
        el.register_ballot(ballot)

    el.run_count(max_rounds=5)
    for candidate_id, candidate in candidates.items():
        logger.info(f"Kandidāts {candidate_id}: status={candidate.status}, kopsumma={candidate.tally}")
