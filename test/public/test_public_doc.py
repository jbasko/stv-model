from decimal import Decimal

from stv_model.example import get_example_election
from stv_model.model import quantize


def test_sākotnējā_dokumentā_iekļautais_piemērs():
    """
    Tests piemēram, kas izmantots ekspertiem izplatītajā dokumentā.
    """
    el = get_example_election()

    el._run_round()
    assert el.num_ballots == 60_000
    assert el.quota == 10_001.0

    ca = el.candidates["A"]
    cb = el.candidates["B"]
    cc = el.candidates["C"]
    cd = el.candidates["D"]
    cf = el.candidates["F"]
    cg = el.candidates["G"]
    assert cf.status == "elected"
    assert cf.tally == 10_001.0

    el._run_round()

    assert cb.status == "elected"
    assert cb.tally == 10_001.0

    el._run_round()

    assert ca.status == "elected"
    assert ca.tally == 10_001.0

    el._run_round()

    assert cg.status == "eliminated"
    assert cg.tally == 0.0

    el._run_round()

    assert cd.status == "eliminated"
    assert cd.tally == 0.0

    el._run_round()

    assert cc.status == "elected"
    assert quantize(cc.tally) == quantize(Decimal("9333.266667"))

    el._run_round()
