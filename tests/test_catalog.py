from aksave.catalog import Catalog, challenges_from_flags

CAT = Catalog.load()


def test_manifest_has_315_items():
    assert len(CAT.items) == 315


def test_expected_per_region_counts():
    counts = {r: len([i for i in CAT.items if i.region == r]) for r in CAT.regions}
    assert counts == {"CityZ": 66, "CityX": 66, "CityY": 66,
                      "Stagg": 39, "Film": 39, "HideOut": 39}


def test_full_set_is_243_challenges():
    assert challenges_from_flags([i.flag for i in CAT.items]) == 243


def test_breakables_credit_one_per_five():
    five = [i.flag for i in CAT.items if i.type == "MilitiaShield"][:5]
    assert challenges_from_flags(five) == 1
    assert challenges_from_flags(five[:4]) == 0


def test_single_breakable_is_zero_challenges():
    """Corpus save 'Save files 5' has 1 object and reads 0/243."""
    one = [i.flag for i in CAT.items if i.type == "InsectCrate"][:1]
    assert challenges_from_flags(one) == 0


def test_mixed_four_objects_is_two_challenges():
    """Corpus 'SF4 / all riddles on map' has 4 objects and reads 2/243."""
    flags = [i.flag for i in CAT.items if i.type == "Pickup"][:2] + \
            [i.flag for i in CAT.items if i.type == "MilitiaShield"][:2]
    assert challenges_from_flags(flags) == 2


def test_rejects_unknown_flag():
    import pytest
    with pytest.raises(KeyError):
        CAT.item("PickedUp_CityZ_Pickup_999")
