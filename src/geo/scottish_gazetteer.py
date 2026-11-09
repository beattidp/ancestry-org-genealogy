"""Scottish Civil Parish Gazetteer and National Records of Scotland (NRS) Place Resolver."""

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScottishParish:
    """Represents an official Scottish Civil Parish and NRS Registration District."""

    parish_number: str
    parish_name: str
    county: str
    alternate_names: list[str] = field(default_factory=list)
    opr_start_year: int = 1553
    latitude: float | None = None
    longitude: float | None = None

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Returns (latitude, longitude) if available."""
        if self.latitude is not None and self.longitude is not None:
            return (self.latitude, self.longitude)
        return None

    def generate_scotlandspeople_url(
        self, surname: str = "", forename: str = "", year: int | None = None
    ) -> str:
        """Generates direct ScotlandsPeople Old Parish Registers (OPR) reference URL."""
        base = "https://www.scotlandspeople.gov.uk/record-results"
        params = {
            "search_type": "people",
            "record_type": "opr_births",
            "surname": surname,
            "forename": forename,
            "county": self.county,
            "rd_real_name": self.parish_name,
            "rd_real_number": self.parish_number,
        }
        if year:
            params["year_from"] = str(max(1538, year - 5))
            params["year_to"] = str(min(1854, year + 5))
        return f"{base}?{urllib.parse.urlencode(params)}"


# Curated reference table of major Scottish historical counties and civil parishes
# based on National Records of Scotland (NRS) civil parish listings on data.gov.scot
SCOTTISH_PARISH_DATA: list[dict[str, Any]] = [
    # Midlothian / Edinburghshire
    {
        "number": "685/1",
        "name": "St Cuthbert's, Edinburgh",
        "county": "Midlothian",
        "alts": ["edinburgh", "st cuthberts", "st cuthbert", "west kirk"],
        "opr_start": 1573,
        "lat": 55.9508,
        "lon": -3.2053,
    },
    {
        "number": "685/2",
        "name": "Canongate, Edinburgh",
        "county": "Midlothian",
        "alts": ["canongate", "edinburgh canongate"],
        "opr_start": 1564,
        "lat": 55.9525,
        "lon": -3.1786,
    },
    {
        "number": "685/3",
        "name": "St Giles, Edinburgh",
        "county": "Midlothian",
        "alts": ["st giles", "high kirk", "edinburgh city"],
        "opr_start": 1595,
        "lat": 55.9495,
        "lon": -3.1908,
    },
    {
        "number": "693",
        "name": "Liberton",
        "county": "Midlothian",
        "alts": ["libberton", "liberton", "libberton midlothian"],
        "opr_start": 1629,
        "lat": 55.9142,
        "lon": -3.1611,
    },
    {
        "number": "692/1",
        "name": "Leith South",
        "county": "Midlothian",
        "alts": ["leith", "south leith", "port of leith"],
        "opr_start": 1597,
        "lat": 55.9715,
        "lon": -3.1718,
    },
    {
        "number": "683",
        "name": "Dalkeith",
        "county": "Midlothian",
        "alts": ["dalkeith"],
        "opr_start": 1603,
        "lat": 55.8928,
        "lon": -3.0706,
    },
    # Argyllshire
    {
        "number": "539",
        "name": "Jura and Colonsay",
        "county": "Argyll",
        "alts": ["colonsay", "oronsay", "jura", "colonsay and oronsay", "isle of colonsay"],
        "opr_start": 1704,
        "lat": 55.9961,
        "lon": -5.9922,
    },
    {
        "number": "506",
        "name": "Campbeltown",
        "county": "Argyll",
        "alts": ["campbeltown", "kinloch", "kintyre"],
        "opr_start": 1659,
        "lat": 55.4244,
        "lon": -5.6061,
    },
    {
        "number": "512",
        "name": "Inveraray",
        "county": "Argyll",
        "alts": ["inveraray", "inverary"],
        "opr_start": 1652,
        "lat": 56.2307,
        "lon": -5.0747,
    },
    {
        "number": "546",
        "name": "Kilchoman (Islay)",
        "county": "Argyll",
        "alts": ["kilchoman", "islay"],
        "opr_start": 1720,
        "lat": 55.7797,
        "lon": -6.4406,
    },
    # Aberdeenshire
    {
        "number": "168/1",
        "name": "St Nicholas, Aberdeen",
        "county": "Aberdeenshire",
        "alts": ["aberdeen", "st nicholas", "aberdeen city"],
        "opr_start": 1563,
        "lat": 57.1475,
        "lon": -2.0988,
    },
    {
        "number": "168/2",
        "name": "Old Machar, Aberdeen",
        "county": "Aberdeenshire",
        "alts": ["old machar", "machar", "old aberdeen"],
        "opr_start": 1641,
        "lat": 57.1697,
        "lon": -2.1031,
    },
    {
        "number": "232",
        "name": "Peterhead",
        "county": "Aberdeenshire",
        "alts": ["peterhead"],
        "opr_start": 1668,
        "lat": 57.5083,
        "lon": -1.7833,
    },
    # Peeblesshire
    {
        "number": "768",
        "name": "Peebles",
        "county": "Peeblesshire",
        "alts": ["peebles", "peebleshire"],
        "opr_start": 1644,
        "lat": 55.6533,
        "lon": -3.1906,
    },
    {
        "number": "764",
        "name": "Innerleithen",
        "county": "Peeblesshire",
        "alts": ["innerleithen"],
        "opr_start": 1660,
        "lat": 55.6186,
        "lon": -3.0636,
    },
    # Lanarkshire / Glasgow
    {
        "number": "644/1",
        "name": "Glasgow (City/Inner High)",
        "county": "Lanarkshire",
        "alts": ["glasgow", "glasgow city", "st mungo"],
        "opr_start": 1609,
        "lat": 55.8625,
        "lon": -4.2425,
    },
    {
        "number": "622",
        "name": "Barony, Glasgow",
        "county": "Lanarkshire",
        "alts": ["barony", "barony parish"],
        "opr_start": 1702,
        "lat": 55.8631,
        "lon": -4.2344,
    },
    {
        "number": "647",
        "name": "Hamilton",
        "county": "Lanarkshire",
        "alts": ["hamilton"],
        "opr_start": 1648,
        "lat": 55.7772,
        "lon": -4.0394,
    },
    {
        "number": "652",
        "name": "Lanark",
        "county": "Lanarkshire",
        "alts": ["lanark"],
        "opr_start": 1646,
        "lat": 55.6738,
        "lon": -3.7781,
    },
    # Ayrshire
    {
        "number": "578",
        "name": "Ayr",
        "county": "Ayrshire",
        "alts": ["ayr"],
        "opr_start": 1661,
        "lat": 55.4627,
        "lon": -4.6292,
    },
    {
        "number": "597",
        "name": "Kilmarnock",
        "county": "Ayrshire",
        "alts": ["kilmarnock"],
        "opr_start": 1640,
        "lat": 55.6111,
        "lon": -4.4958,
    },
    {
        "number": "602",
        "name": "Largs",
        "county": "Ayrshire",
        "alts": ["largs"],
        "opr_start": 1647,
        "lat": 55.7958,
        "lon": -4.8697,
    },
    # Dumfriesshire / Scottish Borders
    {
        "number": "821",
        "name": "Dumfries",
        "county": "Dumfriesshire",
        "alts": ["dumfries"],
        "opr_start": 1605,
        "lat": 55.0709,
        "lon": -3.6053,
    },
    {
        "number": "812",
        "name": "Annan",
        "county": "Dumfriesshire",
        "alts": ["annan"],
        "opr_start": 1703,
        "lat": 54.9867,
        "lon": -3.2592,
    },
    {
        "number": "834",
        "name": "Lochmaben",
        "county": "Dumfriesshire",
        "alts": ["lochmaben"],
        "opr_start": 1765,
        "lat": 55.1294,
        "lon": -3.4447,
    },
    # Clackmannanshire
    {
        "number": "465",
        "name": "Alloa",
        "county": "Clackmannanshire",
        "alts": ["alloa"],
        "opr_start": 1609,
        "lat": 56.1165,
        "lon": -3.7915,
    },
    # Renfrewshire
    {
        "number": "564/3",
        "name": "Greenock West",
        "county": "Renfrewshire",
        "alts": ["greenock", "clyde", "port glasgow"],
        "opr_start": 1698,
        "lat": 55.9567,
        "lon": -4.7633,
    },
    {
        "number": "573",
        "name": "Paisley",
        "county": "Renfrewshire",
        "alts": ["paisley", "paisley abbey"],
        "opr_start": 1676,
        "lat": 55.8456,
        "lon": -4.4239,
    },
]

SCOTTISH_COUNTIES = {
    "aberdeen": "Aberdeenshire",
    "aberdeenshire": "Aberdeenshire",
    "angus": "Angus (Forfarshire)",
    "argyll": "Argyll",
    "argyllshire": "Argyll",
    "ayr": "Ayrshire",
    "ayrshire": "Ayrshire",
    "banff": "Banffshire",
    "banffshire": "Banffshire",
    "berwick": "Berwickshire",
    "berwickshire": "Berwickshire",
    "bute": "Bute",
    "caithness": "Caithness",
    "clackmannan": "Clackmannanshire",
    "clackmannanshire": "Clackmannanshire",
    "dumfries": "Dumfriesshire",
    "dumfriesshire": "Dumfriesshire",
    "dunbarton": "Dunbartonshire",
    "dunbartonshire": "Dunbartonshire",
    "east lothian": "East Lothian (Haddingtonshire)",
    "fife": "Fife",
    "inverness": "Inverness-shire",
    "inverness-shire": "Inverness-shire",
    "kincardine": "Kincardineshire",
    "kincardineshire": "Kincardineshire",
    "kinross": "Kinross-shire",
    "kirkcudbright": "Kirkcudbrightshire",
    "lanark": "Lanarkshire",
    "lanarkshire": "Lanarkshire",
    "midlothian": "Midlothian",
    "edinburghshire": "Midlothian",
    "moray": "Moray (Elginshire)",
    "nairn": "Nairnshire",
    "orkney": "Orkney",
    "peebles": "Peeblesshire",
    "peeblesshire": "Peeblesshire",
    "perth": "Perthshire",
    "perthshire": "Perthshire",
    "renfrew": "Renfrewshire",
    "renfrewshire": "Renfrewshire",
    "ross": "Ross and Cromarty",
    "roxburgh": "Roxburghshire",
    "selkirk": "Selkirkshire",
    "shetland": "Shetland (Zetland)",
    "stirling": "Stirlingshire",
    "stirlingshire": "Stirlingshire",
    "sutherland": "Sutherland",
    "west lothian": "West Lothian (Linlithgowshire)",
    "wigtown": "Wigtownshire",
}


class ScottishGazetteer:
    """Resolver for historical Scottish parishes, counties, and NRS registration districts."""

    def __init__(self) -> None:
        self.parishes: list[ScottishParish] = []
        for d in SCOTTISH_PARISH_DATA:
            self.parishes.append(
                ScottishParish(
                    parish_number=d["number"],
                    parish_name=d["name"],
                    county=d["county"],
                    alternate_names=d["alts"],
                    opr_start_year=d["opr_start"],
                    latitude=d.get("lat"),
                    longitude=d.get("lon"),
                )
            )

    def get_parish_coordinates(self, parish_number: str) -> tuple[float, float] | None:
        """Retrieves latitude and longitude centroid for a given parish number."""
        for p in self.parishes:
            if p.parish_number == parish_number:
                return p.coordinates
        return None

    @staticmethod
    def is_scottish_place(place_str: str | None) -> bool:
        """Determines if a place string references Scotland."""
        if not place_str:
            return False
        clean = place_str.lower()
        if "scotland" in clean:
            return True
        for county in SCOTTISH_COUNTIES:
            if re.search(rf"\b{re.escape(county)}\b", clean):
                return True
        return False

    def resolve_place(self, place_str: str | None) -> tuple[ScottishParish | None, str | None]:
        """Resolves raw place string to (ScottishParish, County).

        Returns:
            tuple of (ScottishParish or None, identified_county or None)
        """
        if not place_str:
            return None, None

        clean = place_str.lower()
        tokens = [t.strip() for t in re.split(r"[,/]+", clean) if t.strip()]

        # 1. Check for known Scottish county in tokens
        detected_county = None
        for t in tokens:
            if t in SCOTTISH_COUNTIES:
                detected_county = SCOTTISH_COUNTIES[t]
                break
            for c_key, c_val in SCOTTISH_COUNTIES.items():
                if re.search(rf"\b{re.escape(c_key)}\b", t):
                    detected_county = c_val
                    break
            if detected_county:
                break

        # 2. Match exact parish or alternate names
        for parish in self.parishes:
            # Check parish name
            p_name_clean = parish.parish_name.lower()
            if re.search(rf"\b{re.escape(p_name_clean)}\b", clean):
                if detected_county and detected_county.lower() != parish.county.lower():
                    continue
                return parish, parish.county

            # Check aliases
            for alt in parish.alternate_names:
                if re.search(rf"\b{re.escape(alt)}\b", clean):
                    if detected_county and detected_county.lower() != parish.county.lower():
                        continue
                    return parish, parish.county

        # If parish not found but county was found
        return None, detected_county
