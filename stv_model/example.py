import logging
import os

from stv_model.model import Candidate, Election, Ballot


def get_example_election():
    candidates = {cid: Candidate(id=cid) for cid in "ABCDEFG"}
    el = Election(
        num_seats=5,
        candidates=candidates,
    )
    el.register_ballot(Ballot(id="a", prefs=("A",), strength=7_500))
    el.register_ballot(Ballot(id="ab", prefs=("A", "B"), strength=1_500))
    el.register_ballot(Ballot(id="ag", prefs=("A", "G"), strength=500))
    el.register_ballot(Ballot(id="b", prefs=("B",), strength=5_800))
    el.register_ballot(Ballot(id="be", prefs=("B", "E"), strength=5_000))
    el.register_ballot(Ballot(id="c", prefs=("C",), strength=9_200))
    el.register_ballot(Ballot(id="d", prefs=("D",), strength=2_000))
    el.register_ballot(Ballot(id="dc", prefs=("D", "C"), strength=4_000))
    el.register_ballot(Ballot(id="dcg", prefs=("D", "C", "G"), strength=1_000))
    el.register_ballot(Ballot(id="e", prefs=("E",), strength=6_800))
    el.register_ballot(Ballot(id="bf", prefs=("F",), strength=3000))
    el.register_ballot(Ballot(id="fa", prefs=("F", "A"), strength=3200))
    el.register_ballot(Ballot(id="fb", prefs=("F", "B"), strength=3000))
    el.register_ballot(Ballot(id="fc", prefs=("F", "C"), strength=800))
    el.register_ballot(Ballot(id="fd", prefs=("F", "D"), strength=200))
    el.register_ballot(Ballot(id="fe", prefs=("F", "E"), strength=1800))
    el.register_ballot(Ballot(id="ga", prefs=("G", "A"), strength=3_000))
    el.register_ballot(Ballot(id="gabef", prefs=("G", "A", "B", "E", "F"), strength=1_700))

    return el


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    election = get_example_election()
    os.system("clear")
    election.run_count(sleep_between_rounds=5.0)
