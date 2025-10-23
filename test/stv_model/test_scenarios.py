from stv_model.model import Election


def test_divi_līderi_pirmajā_skaitīšanas_kārtā_uzreiz_ievēlēti():
    votes = [
        "AC",
        "BC",
        "CB",
        "AB",
        "BAC",
    ]
    election = Election.from_votes(votes=votes, num_seats=2)
    election.run_count()

    assert election.round_no == 1
    assert election.num_elected == 2

    assert election.candidates["A"].is_elected
    assert election.candidates["B"].is_elected
    assert not election.candidates["C"].is_elected

    assert election.candidates["A"].tallies == [2.0]
    assert election.candidates["B"].tallies == [2.0]
    assert election.candidates["C"].tallies == [1.0]


def test_pārpalikuma_pārdale_ar_diviem_ievēlētiem_pirmajā_kārtā():
    votes = [
        "AB",
        "ABD",
        "AC",
        "ACD",  # A - 4, nākamie: D - 1, C - 2. Pārdales koeficients = 4-3/4 = 0.25.
        "B",
        "BC",
        "BCA",
        "BD",  # B - 4, nākamie: D - 1, C - 2. Pārdales koeficients = 4-3/4 = 0.25.
    ]
    election = Election.from_votes(votes=votes, num_seats=3)

    a = election.candidates["A"]
    b = election.candidates["B"]
    c = election.candidates["C"]
    d = election.candidates["D"]

    election._run_round()
    assert election.num_ballots == 8
    assert election.num_seats == 3
    assert election.quota == 3.0

    assert a.is_elected
    assert b.is_elected
    assert not c.is_elected
    assert not d.is_elected
    assert a.tally_before_done == 4.0
    assert b.tally_before_done == 4.0

    assert c.tally == 1.0  # 0 + 0.25 * 2 + 0.25 * 1
    assert d.tally == 0.5  # 0 + 0.25 * 1 + 0.25 * 1

    election._run_round()

    assert c.is_elected
    assert not d.is_elected


def test_pirmajā_kārtā_par_daudz_izslēdzamo():
    """
    Jāievēl ir A un B, jo tie alfabētiski ir pirms C un D.
    Nekādā gadījumā nedrīkst skatīties otrās izvēles (kas šajā piemērā it kā liktu ievēlēt C).
    """
    votes = [
        "BC",
        "BC",
        "BC",
        "CA",
        "CB",
        "CD",
        "DA",
        "DB",
        "DC",
        "AC",
        "AC",
        "AC",
    ]
    election = Election.from_votes(votes=votes, num_seats=2)

    election.run_count()

    assert election.candidates["A"].is_elected
    assert election.candidates["B"].is_elected
    assert not election.candidates["C"].is_elected
    assert not election.candidates["D"].is_elected


def test_neizšķirta_gadījumā_iepriekšējo_kārtu_rezultāti_nosaka_apsvēršanas_secību():
    raise NotImplementedError
