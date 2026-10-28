"""Unit tests for Scottish Civil Parish Gazetteer and Place Resolver."""

from src.geo.scottish_gazetteer import ScottishGazetteer, ScottishParish


def test_is_scottish_place() -> None:
    gaz = ScottishGazetteer()
    assert gaz.is_scottish_place("Liberton, Midlothian, Scotland") is True
    assert gaz.is_scottish_place("Aberdeen, Aberdeenshire, Scotland, United Kingdom") is True
    assert gaz.is_scottish_place("Colonsay, Argyll, Scotland") is True
    assert gaz.is_scottish_place("Edinburgh, Scotland") is True
    assert gaz.is_scottish_place("Peeblesshire, Scotland") is True
    assert gaz.is_scottish_place("Boston, Suffolk, Massachusetts, United States") is False
    assert gaz.is_scottish_place("Redwood Judicial Township, Sonoma, California") is False
    assert gaz.is_scottish_place(None) is False
    assert gaz.is_scottish_place("") is False


def test_resolve_exact_parish_and_county() -> None:
    gaz = ScottishGazetteer()

    # Liberton
    parish, county = gaz.resolve_place("Liberton, Midlothian, Scotland")
    assert parish is not None
    assert parish.parish_name == "Liberton"
    assert parish.parish_number == "693"
    assert county == "Midlothian"

    # Colonsay
    parish, county = gaz.resolve_place("Colonsay, Argyll, Scotland")
    assert parish is not None
    assert parish.parish_name == "Jura and Colonsay"
    assert parish.parish_number == "539"
    assert county == "Argyll"

    # Aberdeen
    parish, county = gaz.resolve_place("Aberdeen, Aberdeenshire, Scotland, United Kingdom")
    assert parish is not None
    assert parish.parish_number == "168/1"
    assert county == "Aberdeenshire"

    # Peebles
    parish, county = gaz.resolve_place("Peebles, Peeblesshire, Scotland")
    assert parish is not None
    assert parish.parish_name == "Peebles"
    assert parish.parish_number == "768"
    assert county == "Peeblesshire"

    # County level only
    parish, county = gaz.resolve_place("Midlothian, Scotland")
    assert parish is None
    assert county == "Midlothian"


def test_scotlandspeople_url_generation() -> None:
    parish = ScottishParish(
        parish_number="693",
        parish_name="Liberton",
        county="Midlothian",
    )
    url = parish.generate_scotlandspeople_url(surname="McGill", forename="William", year=1605)
    assert "https://www.scotlandspeople.gov.uk/record-results" in url
    assert "rd_real_number=693" in url
    assert "rd_real_name=Liberton" in url
    assert "county=Midlothian" in url
    assert "surname=McGill" in url
    assert "forename=William" in url
    assert "year_from=1600" in url
    assert "year_to=1610" in url
