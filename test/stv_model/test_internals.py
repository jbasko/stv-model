import pytest

from stv_model.model import Ballot, Candidate, Election


@pytest.fixture()
def abcd_election():
    candidates = {cid: Candidate(id=cid) for cid in "ABCD"}
    el = Election(seats=2, candidates=candidates)
    return el


def test_ballot_registration_initialises_slices_and_piles(abcd_election):
    abcd_election.register_ballot(Ballot(id="b1", prefs=("A", "B", "C")))
    abcd_election.register_ballot(Ballot(id="b2", prefs=("B", "C")))

    assert len(abcd_election.ballots) == 2
    assert len(abcd_election.ballot_slices) == 2
    assert len(abcd_election.slices) == 2
    assert abcd_election.ballot_slices["b1"] == [1]
    assert abcd_election.ballot_slices["b2"] == [2]

    a_slice = abcd_election.slices[1]
    assert a_slice.assigned_to == "A"
    assert a_slice.ballot_id == "b1"
    assert a_slice.current_idx == 0

    assert abcd_election.slices[2].assigned_to == "B"

    assert len(abcd_election.piles) == 2  # C un D nav pirmajās vietās, tātad nav kaudzes vēl.
    assert set(abcd_election.piles.keys()) == {"A", "B"}
    assert abcd_election.piles["A"] == [1]
    assert abcd_election.piles["B"] == [2]


def test_num_ballots_and_quota_and_tally(abcd_election):
    abcd_election.register_ballot(Ballot(id="b1", prefs=("A", "B", "C")))
    abcd_election.register_ballot(Ballot(id="b2", prefs=("B", "C")))
    abcd_election.register_ballot(Ballot(id="b3", prefs=("A", "D")))
    abcd_election.register_ballot(Ballot(id="b4", prefs=("C", "B", "A")))

    assert abcd_election.seats == 2

    abcd_election._calc_num_ballots()
    assert abcd_election.num_ballots == 4

    abcd_election._calc_quota()
    assert abcd_election.quota == 2  # (4 // (2 + 1)) + 1 = 2

    abcd_election.tally()
    assert abcd_election.candidates["A"].tally == 2.0
    assert abcd_election.candidates["B"].tally == 1.0
    assert abcd_election.candidates["C"].tally == 1.0
    assert abcd_election.candidates["D"].tally == 0.0
