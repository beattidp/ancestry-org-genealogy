"""Date parser for GEDCOM X formal and historical original date representations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class DateEstimate:
    """Represents a parsed genealogical date estimate with uncertainty bounds."""

    year: Optional[int]
    month: Optional[int] = None
    day: Optional[int] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    is_approximate: bool = False
    raw_text: str = ""

    @property
    def exact_date(self) -> Optional[date]:
        """Returns standard datetime.date if year, month, and day are all present and valid."""
        if self.year is not None and self.month is not None and self.day is not None:
            try:
                return date(self.year, self.month, self.day)
            except (ValueError, OverflowError):
                return None
        return None

    def __str__(self) -> str:
        if self.exact_date:
            return self.exact_date.isoformat()
        if self.year is not None and self.month is not None:
            return f"{self.year:04d}-{self.month:02d}"
        if self.year is not None:
            prefix = "abt " if self.is_approximate else ""
            return f"{prefix}{self.year}"
        return self.raw_text or "Unknown"


# Month name mapping
_MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_FORMAL_FULL_RE = re.compile(r"^[+-]?(\d{4})-(\d{2})-(\d{2})$")
_FORMAL_MONTH_RE = re.compile(r"^[+-]?(\d{4})-(\d{2})$")
_FORMAL_YEAR_RE = re.compile(r"^[+-]?(\d{4})$")
_FORMAL_RANGE_RE = re.compile(r"^[+-]?(\d{4})(?:-\d{2}-\d{2})?/[+-]?(\d{4})(?:-\d{2}-\d{2})?$")
_COMPACT_NUMERIC_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_STANDARD_TEXT_RE = re.compile(
    r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", re.IGNORECASE
)
_MONTH_YEAR_TEXT_RE = re.compile(
    r"^([A-Za-z]+)\s+(\d{4})$", re.IGNORECASE
)
_YEAR_ONLY_RE = re.compile(r"\b(\d{4})\b")


def parse_date(
    date_formal: Optional[str] = None,
    date_original: Optional[str] = None,
) -> Optional[DateEstimate]:
    """Parses GEDCOM X date_formal and/or date_original into DateEstimate."""
    # 1. Try date_formal first if present
    if date_formal and date_formal.strip():
        formal = date_formal.strip()

        # Full YYYY-MM-DD
        m = _FORMAL_FULL_RE.match(formal)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return DateEstimate(
                year=y,
                month=mo,
                day=d,
                min_year=y,
                max_year=y,
                is_approximate=False,
                raw_text=formal,
            )

        # Year and Month YYYY-MM
        m = _FORMAL_MONTH_RE.match(formal)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
            return DateEstimate(
                year=y,
                month=mo,
                day=None,
                min_year=y,
                max_year=y,
                is_approximate=False,
                raw_text=formal,
            )

        # Range YYYY/YYYY
        m = _FORMAL_RANGE_RE.match(formal)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            avg_y = (y1 + y2) // 2
            return DateEstimate(
                year=avg_y,
                min_year=y1,
                max_year=y2,
                is_approximate=True,
                raw_text=formal,
            )

        # Year only YYYY
        m = _FORMAL_YEAR_RE.match(formal)
        if m:
            y = int(m.group(1))
            return DateEstimate(
                year=y,
                min_year=y,
                max_year=y,
                is_approximate=False,
                raw_text=formal,
            )

    # 2. Try date_original
    if date_original and date_original.strip():
        orig = date_original.strip()
        orig_lower = orig.lower()
        is_approx = any(p in orig_lower for p in ["abt", "about", "circa", "c.", "bef", "aft", "est"])

        # Check ISO YYYY-MM-DD or +YYYY-MM-DD in original
        m = _FORMAL_FULL_RE.match(orig)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return DateEstimate(
                year=y,
                month=mo,
                day=d,
                min_year=y,
                max_year=y,
                is_approximate=is_approx,
                raw_text=orig,
            )

        # Check ISO YYYY-MM
        m = _FORMAL_MONTH_RE.match(orig)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
            return DateEstimate(
                year=y,
                month=mo,
                day=None,
                min_year=y,
                max_year=y,
                is_approximate=is_approx,
                raw_text=orig,
            )

        # Compact numeric 19660421
        m = _COMPACT_NUMERIC_RE.match(orig)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return DateEstimate(
                year=y,
                month=mo,
                day=d,
                min_year=y,
                max_year=y,
                is_approximate=is_approx,
                raw_text=orig,
            )

        # "22 November 1919" or "7 Jan 1922"
        m = _STANDARD_TEXT_RE.match(orig)
        if m:
            d = int(m.group(1))
            month_name = m.group(2).lower()
            mo = _MONTH_NAMES.get(month_name)
            y = int(m.group(3))
            if mo:
                return DateEstimate(
                    year=y,
                    month=mo,
                    day=d,
                    min_year=y,
                    max_year=y,
                    is_approximate=is_approx,
                    raw_text=orig,
                )

        # "Jul 1937"
        m = _MONTH_YEAR_TEXT_RE.match(orig)
        if m:
            month_name = m.group(1).lower()
            mo = _MONTH_NAMES.get(month_name)
            y = int(m.group(2))
            if mo:
                return DateEstimate(
                    year=y,
                    month=mo,
                    day=None,
                    min_year=y,
                    max_year=y,
                    is_approximate=is_approx,
                    raw_text=orig,
                )

        # Fallback: Extract any 4-digit year from string
        years = [int(yr) for yr in _YEAR_ONLY_RE.findall(orig)]
        if len(years) == 1:
            y = years[0]
            return DateEstimate(
                year=y,
                min_year=y,
                max_year=y,
                is_approximate=is_approx,
                raw_text=orig,
            )
        elif len(years) > 1:
            y1, y2 = min(years), max(years)
            avg_y = (y1 + y2) // 2
            return DateEstimate(
                year=avg_y,
                min_year=y1,
                max_year=y2,
                is_approximate=True,
                raw_text=orig,
            )

    return None


def calculate_age_in_years(
    birth: Optional[DateEstimate],
    event: Optional[DateEstimate],
) -> Optional[float]:
    """Calculates age in years between birth and an event date.

    Uses exact date arithmetic if both dates are full, or year arithmetic if approximate.
    Returns negative values if event occurs before birth.
    """
    if birth is None or event is None:
        return None

    if birth.exact_date and event.exact_date:
        days = (event.exact_date - birth.exact_date).days
        return round(days / 365.25, 2)

    if birth.year is not None and event.year is not None:
        # If months are present, compute partial year
        if birth.month is not None and event.month is not None:
            mo_diff = event.month - birth.month
            return round((event.year - birth.year) + (mo_diff / 12.0), 2)
        return float(event.year - birth.year)

    return None


def calculate_days_between(
    earlier: Optional[DateEstimate],
    later: Optional[DateEstimate],
) -> Optional[int]:
    """Calculates difference in days from earlier to later.

    Positive means later is after earlier. Negative means later is before earlier.
    """
    if earlier is None or later is None:
        return None

    if earlier.exact_date and later.exact_date:
        return (later.exact_date - earlier.exact_date).days

    if earlier.year is not None and later.year is not None:
        # Approximate using days in year
        y_diff = later.year - earlier.year
        mo_diff = (later.month or 6) - (earlier.month or 6)
        day_diff = (later.day or 15) - (earlier.day or 15)
        return int(round(y_diff * 365.25 + mo_diff * 30.4 + day_diff))

    return None
