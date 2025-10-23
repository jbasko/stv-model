import dataclasses
import itertools
import logging
import math
from typing import Literal


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
    tally: float = 0.0


class Sort:
    @staticmethod
    def by_tally_desc(candidate: Candidate):
        return -candidate.tally


class Election:
    """
    Vēlēšanas (vienā apgabalā).

    Piešķīrums ("šķēle", _slice_ angliski) ir iekšējs objekts un tam nav juridiskas nozīmes vēlēšanu procesā.
    """

    def __init__(
        self,
        *,
        seats: int,
        candidates: dict[CandidateId, Candidate] = None,
    ):
        # Mandātu skaits
        self.seats = seats

        # Droop kvota
        self.quota: float = None

        # Pašreizējā skaitīšanas kārta
        self.round_no = 0

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
                logger.info(f"Pārdale par labu {candidate_id}: +{weight}")
                return next_slice
            next_idx += 1

        return None

    def _next_slice_id(self) -> SliceId:
        slice_id = self._slice_id
        self._slice_id += 1
        return slice_id

    @property
    def num_elected(self):
        return sum(1 for c in self.candidates.values() if c.status == "elected")

    @property
    def num_to_elect(self):
        return self.seats - self.num_elected

    @property
    def num_running(self):
        return sum(1 for c in self.candidates.values() if c.status == "running")

    def tally(self):
        """
        Saskaita balsis visiem kandidātiem.
        """
        for c in self.candidates.values():
            c.tally = 0.0
        for candidate_id, pile in self.piles.items():
            self.candidates[candidate_id].tally = math.fsum(
                self.slices[slice_id].weight for slice_id in pile
            )

    def elect(self, candidate_id: CandidateId):
        candidate = self.candidates[candidate_id]
        surplus = candidate.tally - self.quota
        candidate.status = "elected"
        logger.info(
            f"Kārtā Nr. {self.round_no} ievēlēts kandidāts {candidate_id} "
            f"ar balsu kopsummu {candidate.tally}, pārpalikums {surplus}."
        )
        if surplus <= 0:
            return

        """
        Pārpalikuma pārdale.
        Pārdales koeficients = pārpalikums / kopsumma
        """
        transfer_quotient = surplus / candidate.tally
        remaining_quotient = 1.0 - transfer_quotient

        logger.info(f"Pārdales koeficients: {transfer_quotient}.")

        pile = list(self.piles.get(candidate.id, []))

        for slice_id in pile:
            """
            Esošajam piešķīrumam jāsamazina svars.
            """
            slice = self.slices[slice_id]
            original_weight = slice.weight
            slice.weight *= remaining_quotient

            self._build_next_slice(slice, weight=transfer_quotient * original_weight, reason="elected")

        ...

    def eliminate(self, candidate_id: CandidateId):
        candidate = self.candidates[candidate_id]
        candidate.status = "eliminated"

        # Iztukšojam kaudzi pilnībā.
        logger.info(f"Izslēdzam kandidātu {candidate_id} ar šī brīža balsu kopsummu {candidate.tally}.")
        pile = list(self.piles.get(candidate.id, []))
        self.piles[candidate.id] = []

        for slice_id in pile:
            slice = self.slices[slice_id]
            transfer_value = slice.weight
            slice.weight = 0.0
            self._build_next_slice(slice, weight=transfer_value, reason="eliminated")


    def _get_candidates_by_tally(self):
        """
        Atgriež kandidātus sakārtotus pēc balsu kopsummas dilstošā secībā
        un neizšķirtu gadījumā pēc viņu rezultāta iepriekšējā(s) skaitīšanas kārtā.
        """
        for tally, candidates_group in itertools.groupby(sorted(self.candidates.values(), key=Sort.by_tally_desc), Sort.by_tally_desc):
            candidates = list(candidates_group)
            if len(candidates) > 1:
                # TODO Ir neizšķirts! Pagaidām alfabētiskā secībā.
                ...
                if tally != self.quota:
                    logger.warning(f"Neizšķirts starp vairākiem kandidātiem ar balsu kopsummu {tally}")
                yield from sorted(candidates, key=lambda c: c.id)
            else:
                yield from candidates

    def _calc_num_ballots(self):
        self.num_ballots = int(sum(ballot.strength for ballot in self.ballots.values() if ballot.is_valid))

    def _calc_quota(self):
        self.quota = math.floor(self.num_ballots / (self.seats + 1)) + 1.0

    def _log_counts(self):
        for candidate_id, candidate in self.candidates.items():
            logger.info(
                f"{candidate_id}: {candidate.tally} "
                f"{'IEVĒLĒTS' if candidate.status == 'elected' else ''}"
                f"{'IZSLĒGTS' if candidate.status == 'eliminated' else ''}"
            )

    def run_count(self, max_rounds=100):
        self.round_no = 0

        while self.num_elected < self.seats and self.round_no < max_rounds:
            self._run_round()

        if self.round_no >= max_rounds:
            logger.warning(f"Sasniegts maksimālais skaitīšanas kārtu skaits ({max_rounds}).")

    def _run_round(self):
        if self.round_no == 0:
            self._calc_num_ballots()
            self._calc_quota()

            logger.info(
                f"Skaitīšana sākusies. Mandātu skaits: {self.seats}, "
                f"derīgās vēlēšanu zīmes: {self.num_ballots}, kvota: {self.quota}, "
                f"ievēlēti: {self.num_elected}."
            )

            self.tally()
            self._log_counts()

        self.round_no += 1
        ranked_candidates = list(c for c in self._get_candidates_by_tally() if c.status == "running")

        elected = [
            c.id
            for c in ranked_candidates
            if c.status == "running" and c.tally >= self.quota
        ]
        if elected:
            self.elect(elected[0])  # Tikai viens ievēlētais katrā kārtā
        else:
            if self.num_to_elect == self.num_running:
                logger.info(
                    f"Atlikušie ({self.num_running}) kandidāti visi ir ievēlēti, "
                    f"jo brīvo mandātu skaits ir {self.num_to_elect}."
                )
                for c in ranked_candidates:
                    self.elect(c.id)
                self.tally()
                self._log_counts()
                logger.info("********************************************************************")
                return

            logger.warning("Neviens kandidāts netika ievēlēts šajā kārtā. Notiks izslēgšana.")
            """
            TODO
            Nav pareizi izslēgt uzreiz visus, kam ir nulle balsu?
            Laikam nē, jo var gadīties, ka kandidāts visiem ir otrā izvēle!
            """
            # Izslēdzam uzreiz visus, kuriem vispār nav balsu TODO Te vajag algoritmisku precizēšanu!
            self.eliminate(ranked_candidates[-1].id)

        self.tally()
        self._log_counts()

        logger.info("********************************************************************")
