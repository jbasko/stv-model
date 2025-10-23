import dataclasses
import itertools
import logging
import math
import os
import time
from typing import Literal, Self, Sequence

logger = logging.getLogger(__name__)

BallotId = str
CandidateId = str
SliceId = int
Reason = Literal["elected", "eliminated"]


@dataclasses.dataclass(frozen=True)
class Ballot:
    """
    Vēlēšanu zīme. Nemainīgs objekts.
    """
    id: BallotId
    prefs: tuple[CandidateId, ...]

    # Normāli katrai balsij vērtība ir 1.0, bet testēšanai un simulācijām ir ērti to mainīt.
    # Piemēram, viena vēlēšanu zīme var reprezentēt 1000 identiskas vēlēšanu zīmes.
    strength: float = 1.0

    @property
    def is_valid(self) -> bool:
        return self.strength > 0 and len(self.prefs) > 0


@dataclasses.dataclass
class Slice:
    id: SliceId
    ballot_id: BallotId
    current_idx: int = 0  # Indekss vēlēšanu zīmes preferenču sarakstā
    weight: float = 1.0
    assigned_to: CandidateId | None = None
    last_transfer_round: int | None = None
    last_transfer_reason: Reason | None = None


@dataclasses.dataclass
class Candidate:
    """
    Kandidāta stāvoklis cauri skaitīšanas kārtām.
    """
    id: CandidateId
    status: Literal["running", "elected", "eliminated"] = "running"
    tallies: list[float] = dataclasses.field(default_factory=lambda: [0.0])

    # Balsu kopsumma brīdī, kad kandidāts beidz dalību (ievēlēts vai izslēgts).
    tally_before_done: float = 0.0

    @property
    def tally(self) -> float:
        if not self.tallies:
            return 0.0
        return self.tallies[-1]

    @property
    def is_elected(self) -> bool:
        return self.status == "elected"

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def is_eliminated(self) -> bool:
        return self.status == "eliminated"


class Key:
    @staticmethod
    def by_tally_desc_then_id(candidate: Candidate):
        """
        Atslēga kandidātu salīdzināšanai neizšķirta gadījumā, izmantojot iepriekšējo kārtu rezultātus,
        un pašās beigās kandidāta ID alfabētisko secību.
        """
        return tuple([-1 * t for t in reversed(candidate.tallies)]), candidate.id


class Election:
    """
    Vēlēšanas (vienā apgabalā).

    Piešķīrums ("šķēle", _slice_ angliski) ir iekšējs objekts un tam nav juridiskas nozīmes vēlēšanu procesā.
    """

    @classmethod
    def from_votes(cls, *, votes: list[Sequence[CandidateId]] | str, num_seats: int) -> Self:
        if isinstance(votes, str):
            votes = [line.strip() for line in votes.splitlines(keepends=False)]
        election = cls(num_seats=num_seats)
        for i, prefs in enumerate(votes, start=1):
            for pref in prefs:
                if pref not in election.candidates:
                    election.register_candidate(Candidate(id=pref))
            ballot = Ballot(id=str(i), prefs=tuple(prefs))
            election.register_ballot(ballot)
        return election

    def __init__(
        self,
        *,
        num_seats: int,
        candidates: dict[CandidateId, Candidate] = None,
    ):
        # Mandātu skaits
        self.num_seats = num_seats

        # Droop kvota
        self.quota: int = None

        # Pašreizējā skaitīšanas kārta, numurēta no 0.
        # "-1" nozīmē, ka skaitīšana vēl nav sākusies.
        # Skatīt arī self.round_no, kas ir faktiskais kārtas numurs, sākot no 1.
        self._round_idx = -1

        # Dinamiski aprēķināts derīgo vēlēšanu zīmju skaits
        self.num_ballots: int = None

        # Visi kandidāti
        self.candidates: dict[CandidateId, Candidate] = {}

        # Visas vēlēšanu zīmes
        self.ballots: dict[BallotId, Ballot] = {}

        # Visi vēlēšanu zīmju piešķīrumi kandidātiem.
        self.slices: dict[SliceId, Slice] = {}

        # Vēlēšanu zīmju piešķīrumi kandidātiem pēc vēlēšanu zīmes ID
        self.ballot_slices: dict[BallotId, list[SliceId]] = {}

        # Kaudzes ar vēlēšanu zīmju piešķīrumiem pēc kandidāta ID
        self.piles: dict[CandidateId, list[SliceId]] = {}

        # Piešķīrumu ID ģenerēšanai
        self._slice_id: SliceId = 1

        if candidates:
            for candidate in candidates.values():
                self.register_candidate(candidate)

    def register_candidate(self, candidate: Candidate):
        assert candidate.id not in self.candidates
        self.candidates[candidate.id] = candidate

    def register_ballot(self, ballot: Ballot):
        assert ballot.id not in self.ballots
        assert ballot.id not in self.ballot_slices
        self.ballots[ballot.id] = ballot
        self._create_slice(ballot)

    def reset(self):
        """
        Atiestata skaitīšanas stāvokli, lai varētu sākt no jauna.
        """
        self._round_idx = 0
        self.num_ballots = None
        self.quota = None
        self.slices = {}
        self.ballot_slices = {}
        self.piles = {}
        self._slice_id = 1

        for candidate in self.candidates.values():
            candidate.status = "running"
            candidate.tallies = []

        for ballot in self.ballots.values():
            self._create_slice(ballot)

    def run_count(self, *, max_rounds=100, sleep_between_rounds: float = 0.0):
        """
        Galvenā skaitīšana.
        """
        assert self.round_no == 0, "Pilno skaitīšanu var veikt tikai vienu reizi."

        while self.num_elected < self.num_seats and self.round_no < max_rounds:
            self._run_round()

            # Demo ģenerēšanai
            if sleep_between_rounds:
                time.sleep(sleep_between_rounds)
                os.system("clear")

        if self.round_no >= max_rounds:
            logger.warning(f"Sasniegts maksimālais skaitīšanas kārtu skaits ({max_rounds}).")

    def _run_round(self):
        """
        Veic vienu skaitīšanas kārtu.
        """
        self._round_idx += 1

        if self.num_elected >= self.num_seats:
            logger.warning("Visi mandāti jau ir piešķirti.")
            return

        if self.round_no == 1:
            self._calc_num_ballots()
            self._calc_quota()

            logger.info(
                f"Sākam skaitīšanu. "
                f"Mandātu skaits: {self.num_seats}, "
                f"derīgās vēlēšanu zīmes: {self.num_ballots}, "
                f"kvota: {self.quota}."
            )

            self.run_tally()

        ranked_candidates = list(c for c in self._get_candidates_by_tally() if c.is_running)
        assert ranked_candidates, "Nav kandidātu, kuri varētu tikt ievēlēti vai izslēgti."

        elected = [
            c.id
            for c in ranked_candidates
            if c.is_running and c.tally >= self.quota
        ]

        if elected:
            # Vispirms atzīmē kā ievēlētus un tikai tad pārdala pārpalikumu,
            # jo pārdalei jānotiek tikai starp vēl aktīvajiem kandidātiem.

            for candidate_id in elected:
                self.candidates[candidate_id].status = "elected"

            for candidate_id in elected:
                self.elect(candidate_id)

            if self.num_to_elect == self.num_running:
                self._finish_run()
                return

        else:
            # Ir jāizslēdz kāds kandidāts.

            if self.num_to_elect == self.num_running - 1:
                # Tieši viens jāizslēdz, pārējie ievēlēti.
                to_eliminate = ranked_candidates[-1].id
                self.eliminate(to_eliminate, transfer_surplus=False)
                self._finish_run()
                return

            if self.num_to_elect == self.num_running:
                self._finish_run()
                return

            # Ja ir vairāki kandidāti ar pašu mazāko balsu kopsummu, visi ir potenciāli izslēdzami.
            # Taču nedrīkst veikt izslēgšanu, ja pēc izslēgšanas būs par maz kandidātu atlikuši.
            smallest_tally = ranked_candidates[-1].tally
            eliminable = [
                c.id
                for c in reversed(ranked_candidates)
                if c.tally == smallest_tally  # TODO floating point precizitātes jautājums!!
            ]

            if len(eliminable) > 1:
                logger.warning(
                    f"Neizšķirts starp vairākiem kandidātiem ar balsu kopsummu {smallest_tally:.3f} "
                    f"par izslēgšanu."
                )
            for candidate_id in eliminable[:self.num_running - self.num_to_elect]:
                self.eliminate(candidate_id)

            if self.num_to_elect == self.num_running:
                self._finish_run()
                return

        self.run_tally()
        self._log_counts()

        logger.info("********************************************************************")

    def _finish_run(self):
        if self.num_to_elect == self.num_running:
            # Ievēlam visus atlikušos.
            for c in self.candidates.values():
                if c.is_running:
                    self.elect(c.id, transfer_surplus=False)  # Nav jēgas pārdalīt pārpalikumu.

        self.run_tally()
        self._log_counts()
        logger.info("********************************************************************")

    def _create_slice(self, ballot: Ballot) -> Slice | None:
        if not ballot.is_valid:
            # Nederīga vēlēšanu zīme, nav vērts neko sīkāk glabāt.
            return None

        first_pref = ballot.prefs[0]  # Derīgā zīmē jābūt vismaz vienam kandidātam

        slice = Slice(
            id=self._next_slice_id(),
            ballot_id=ballot.id,
            current_idx=0,
            weight=ballot.strength,
            assigned_to=first_pref,
        )
        self.slices[slice.id] = slice
        self.ballot_slices.setdefault(ballot.id, []).append(slice.id)
        self.piles.setdefault(first_pref, []).append(slice.id)
        return slice

    def _build_next_slice(self, slice: Slice, weight: float, reason: Reason) -> Slice | None:
        ballot = self.ballots[slice.ballot_id]
        next_idx = slice.current_idx + 1
        while next_idx < len(ballot.prefs):
            candidate_id = ballot.prefs[next_idx]
            candidate = self.candidates[candidate_id]
            if candidate.status == "running" and candidate.tally < self.quota:
                next_slice = Slice(
                    id=self._next_slice_id(),
                    ballot_id=ballot.id,
                    current_idx=next_idx,
                    weight=weight,
                    assigned_to=candidate_id,
                    last_transfer_round=self.round_no,
                    last_transfer_reason=reason,
                )
                self.slices[next_slice.id] = next_slice
                self.ballot_slices.setdefault(ballot.id, []).append(next_slice.id)
                self.piles.setdefault(candidate_id, []).append(next_slice.id)
                logger.info(f"Pārdale par labu {candidate_id!r}: +{weight:.3f}")
                return next_slice
            next_idx += 1

        return None

    def _next_slice_id(self) -> SliceId:
        slice_id = self._slice_id
        self._slice_id += 1
        return slice_id

    @property
    def round_no(self) -> int:
        return self._round_idx + 1

    @property
    def num_elected(self):
        return sum(1 for c in self.candidates.values() if c.status == "elected")

    @property
    def num_to_elect(self):
        return self.num_seats - self.num_elected

    @property
    def num_running(self):
        return sum(1 for c in self.candidates.values() if c.status == "running")

    def run_tally(self):
        """
        Saskaita balsis visiem kandidātiem.
        Ir droši izsaukt vairākas reizes vienas kārtas laikā.
        """
        for candidate_id, pile in self.piles.items():
            candidate = self.candidates[candidate_id]
            tally = math.fsum(
                self.slices[slice_id].weight for slice_id in pile
            )
            if not candidate.tallies or len(candidate.tallies) < self.round_no:
                candidate.tallies.append(tally)
            else:
                candidate.tallies[self._round_idx] = tally

    def elect(self, candidate_id: CandidateId, *, transfer_surplus: bool = True):
        candidate = self.candidates[candidate_id]
        candidate.status = "elected"

        surplus = candidate.tally - self.quota
        candidate.tally_before_done = candidate.tally
        logger.info(
            f"Kārtā Nr. {self.round_no} ievēlēts kandidāts {candidate_id!r} "
            f"ar balsu kopsummu {candidate.tally:.3f}, "
            f"pārpalikums {surplus if surplus >= 0 else 'ir negatīvs'}."
        )
        if not transfer_surplus or surplus <= 0:
            return

        """
        Pārpalikuma pārdale.
        Pārdales koeficients = pārpalikums / kopsumma.
        
        Sākotnējais piešķīrums tiek samazināts par (1 - pārdales koeficients),
        """
        transfer_quotient = surplus / candidate.tally
        remaining_quotient = 1.0 - transfer_quotient

        logger.info(f"Pārdales koeficients: {transfer_quotient:.3f}.")

        pile = list(self.piles.get(candidate.id, []))

        for slice_id in pile:
            """
            Esošajam piešķīrumam jāsamazina svars.
            """
            slice = self.slices[slice_id]
            original_weight = slice.weight
            slice.weight *= remaining_quotient

            self._build_next_slice(slice, weight=transfer_quotient * original_weight, reason="elected")

    def eliminate(self, candidate_id: CandidateId, *, transfer_surplus: bool = True):
        candidate = self.candidates[candidate_id]
        candidate.status = "eliminated"

        pile = list(self.piles.get(candidate.id, []))
        self.piles[candidate.id] = []  # Iztukšojam kaudzi pilnībā.

        if not transfer_surplus:
            logger.info(
                f"Izslēdzam kandidātu {candidate_id!r} ar šī brīža balsu kopsummu {candidate.tally:.3f} bez pārdales."
            )
            return

        logger.info(f"Izslēdzam kandidātu {candidate_id!r}, pārdalot viņa šī brīža balsu kopsummu {candidate.tally:.3f}.")

        for slice_id in pile:
            slice = self.slices[slice_id]
            transfer_value = slice.weight
            slice.weight = 0.0
            self._build_next_slice(slice, weight=transfer_value, reason="eliminated")

    def _calc_num_ballots(self):
        self.num_ballots = int(sum(ballot.strength for ballot in self.ballots.values() if ballot.is_valid))

    def _calc_quota(self):
        self.quota = math.floor(self.num_ballots / (self.num_seats + 1)) + 1

    def _log_counts(self):
        for candidate_id in sorted(self.candidates.keys()):
            candidate = self.candidates[candidate_id]
            logger.info(
                f"{candidate_id}: {candidate.tally:.3f} "
                f"{'✅ IEVĒLĒTS' if candidate.status == 'elected' else ''}"
                f"{'❌ IZSLĒGTS' if candidate.status == 'eliminated' else ''}"
            )

    def _get_candidates_by_tally(self):
        """
        Atgriež kandidātus sakārtotus pēc balsu kopsummas dilstošā secībā
        un neizšķirtu gadījumā pēc viņu rezultāta iepriekšējā(s) skaitīšanas kārtā,
        vai pēc ID, ja arī iepriekšējā(s) kārtā(s) ir neizšķirts.

        Pirmajā kārtā neizšķirtu gadījumā kandidāti tiek sakārtoti alfabētiskā secībā pēc ID.

        NEKĀDĀ GADĪJUMĀ nedrīkst izmantot nākamo kārtu rezultātus, jo tie vēl nav zināmi!
        Tas var novest pie apburta loka. Tāda ir starptautiskā prakse.
        """
        for _, candidates_group in itertools.groupby(
            sorted(self.candidates.values(), key=Key.by_tally_desc_then_id),
            Key.by_tally_desc_then_id,
        ):
            candidates = list(candidates_group)
            yield from candidates
