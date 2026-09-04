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


def test_breakables_are_credited_per_region_not_globally():
    """The corpus contains a save where the two rules disagree.

    `Riddler 183/BAK1Save2x2.sgd` holds part-finished breakable groups in
    several regions at once; the game's own counter says 166, and summing all
    breakables before dividing gives 167. Getting this wrong now puts a wrong
    number on the HUD, because the editor writes that counter string.
    """
    shields = [i.flag for i in CAT.items if i.type == "MilitiaShield"]
    a = [f for f in shields if f.split("_")[1] == "CityX"][:4]
    b = [f for f in shields if f.split("_")[1] == "CityY"][:4]
    assert challenges_from_flags(a + b) == 0        # global rule would say 1


def test_trophies_by_region_counts_only_pickups():
    from aksave.catalog import trophies_by_region
    flags = [i.flag for i in CAT.items
             if i.region == "HideOut" and i.type in ("Pickup", "MiniDrone")]
    assert trophies_by_region(flags) == {"HideOut": 21}
