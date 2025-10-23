def test_readme_md_example():
    from stv_model.model import Election

    el = Election.from_votes(votes="""
        ab
        abc
        ace
        b
        b
        bca
        bcade
        cde
        ce
        ced
    """, num_seats=2)


    el.run_count()
    assert el.quota == 4

    assert el.candidates["a"].is_elected
    assert el.candidates["b"].is_elected
    assert not el.candidates["c"].is_elected
    assert not el.candidates["d"].is_elected
    assert not el.candidates["e"].is_elected
