"""Genealogical biological and chronological validation rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.constraints.date_parser import (
    DateEstimate,
    calculate_age_in_years,
    calculate_days_between,
    parse_date,
)


@dataclass
class Violation:
    """Represents a single constraint or biological anomaly violation."""

    rule_id: str
    severity: str  # ERROR, WARNING, INFO
    person_pid: str
    relative_pid: Optional[str]
    description: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "person_pid": self.person_pid,
            "relative_pid": self.relative_pid,
            "description": self.description,
            "details": self.details,
        }


def _extract_primary_facts(person: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Optional[DateEstimate]]:
    """Extracts parsed DateEstimate objects for primary life events."""
    events: dict[str, Optional[DateEstimate]] = {
        "birth": None,
        "christening": None,
        "death": None,
        "burial": None,
    }

    # First check person table columns
    if person.get("birth_date"):
        events["birth"] = parse_date(date_original=person["birth_date"])
    if person.get("death_date"):
        events["death"] = parse_date(date_original=person["death_date"])

    # Overwrite / refine with detailed fact records
    for f in facts:
        ftype = (f.get("fact_type") or "").lower()
        formal = f.get("date_formal")
        orig = f.get("date_original")
        parsed = parse_date(date_formal=formal, date_original=orig)
        if not parsed:
            continue

        if "birth" in ftype and (events["birth"] is None or parsed.exact_date):
            events["birth"] = parsed
        elif "christen" in ftype or "bapt" in ftype:
            events["christening"] = parsed
        elif "death" in ftype and (events["death"] is None or parsed.exact_date):
            events["death"] = parsed
        elif "burial" in ftype or "cremat" in ftype or "inter" in ftype:
            events["burial"] = parsed

    return events


def check_individual_chronology(
    person: dict[str, Any],
    facts: list[dict[str, Any]],
) -> list[Violation]:
    """Validates chronology of life events and lifespan for a single individual."""
    violations: list[Violation] = []
    pid = person["pid"]
    events = _extract_primary_facts(person, facts)

    birth = events["birth"]
    death = events["death"]
    christening = events["christening"]
    burial = events["burial"]

    # 1. Lifespan check & Death before Birth
    if birth and death:
        if birth.exact_date and death.exact_date:
            if death.exact_date < birth.exact_date:
                days = (birth.exact_date - death.exact_date).days
                violations.append(
                    Violation(
                        rule_id="CHRONO-EVENT-ORDER",
                        severity="ERROR",
                        person_pid=pid,
                        relative_pid=None,
                        description=(
                            f"Death precedes birth date by {days} days "
                            f"(Birth: {birth}, Death: {death})"
                        ),
                        details={"birth": str(birth), "death": str(death), "days_diff": days},
                    )
                )
        elif birth.year is not None and death.year is not None:
            if death.year < birth.year or (
                death.year == birth.year
                and death.month is not None
                and birth.month is not None
                and death.month < birth.month
            ):
                violations.append(
                    Violation(
                        rule_id="CHRONO-EVENT-ORDER",
                        severity="ERROR",
                        person_pid=pid,
                        relative_pid=None,
                        description=(
                            f"Death precedes birth (Birth: {birth}, Death: {death})"
                        ),
                        details={"birth": str(birth), "death": str(death)},
                    )
                )

        age_at_death = calculate_age_in_years(birth, death)
        if age_at_death is not None and age_at_death >= 0:
            if age_at_death > 120.0:
                violations.append(
                    Violation(
                        rule_id="CHRONO-LIFESPAN",
                        severity="ERROR",
                        person_pid=pid,
                        relative_pid=None,
                        description=(
                            f"Lifespan of {age_at_death:.1f} years exceeds biological maximum of 120 years "
                            f"(Birth: {birth}, Death: {death})"
                        ),
                        details={
                            "birth": str(birth),
                            "death": str(death),
                            "age_at_death": age_at_death,
                        },
                    )
                )
            elif age_at_death > 105.0:
                violations.append(
                    Violation(
                        rule_id="CHRONO-LIFESPAN",
                        severity="WARNING",
                        person_pid=pid,
                        relative_pid=None,
                        description=(
                            f"Centenarian lifespan of {age_at_death:.1f} years; requires primary record verification "
                            f"(Birth: {birth}, Death: {death})"
                        ),
                        details={
                            "birth": str(birth),
                            "death": str(death),
                            "age_at_death": age_at_death,
                        },
                    )
                )

    # 2. Christening before Birth check
    if birth and christening:
        if christening.exact_date and birth.exact_date:
            if christening.exact_date < birth.exact_date:
                days = (birth.exact_date - christening.exact_date).days
                if days > 1:
                    violations.append(
                        Violation(
                            rule_id="CHRONO-EVENT-ORDER",
                            severity="ERROR",
                            person_pid=pid,
                            relative_pid=None,
                            description=(
                                f"Christening/Baptism precedes birth date by {days} days "
                                f"(Christening: {christening}, Birth: {birth})"
                            ),
                            details={
                                "christening": str(christening),
                                "birth": str(birth),
                                "days_diff": days,
                            },
                        )
                    )
        elif christening.year is not None and birth.year is not None:
            if christening.year < birth.year or (
                christening.year == birth.year
                and christening.month is not None
                and birth.month is not None
                and christening.month < birth.month
            ):
                violations.append(
                    Violation(
                        rule_id="CHRONO-EVENT-ORDER",
                        severity="ERROR",
                        person_pid=pid,
                        relative_pid=None,
                        description=(
                            f"Christening/Baptism precedes birth (Christening: {christening}, Birth: {birth})"
                        ),
                        details={"christening": str(christening), "birth": str(birth)},
                    )
                )

    # 3. Burial before Death check
    if death and burial:
        if burial.exact_date and death.exact_date:
            if burial.exact_date < death.exact_date:
                days = (death.exact_date - burial.exact_date).days
                if days > 0:
                    violations.append(
                        Violation(
                            rule_id="CHRONO-EVENT-ORDER",
                            severity="ERROR",
                            person_pid=pid,
                            relative_pid=None,
                            description=(
                                f"Burial precedes death date by {days} days "
                                f"(Burial: {burial}, Death: {death})"
                            ),
                            details={
                                "burial": str(burial),
                                "death": str(death),
                                "days_diff": days,
                            },
                        )
                    )
        elif burial.year is not None and death.year is not None:
            if burial.year < death.year or (
                burial.year == death.year
                and burial.month is not None
                and death.month is not None
                and burial.month < death.month
            ):
                violations.append(
                    Violation(
                        rule_id="CHRONO-EVENT-ORDER",
                        severity="ERROR",
                        person_pid=pid,
                        relative_pid=None,
                        description=(
                            f"Burial precedes death date (Burial: {burial}, Death: {death})"
                        ),
                        details={"burial": str(burial), "death": str(death)},
                    )
                )

    return violations


def check_parent_child_biology(
    parent: dict[str, Any],
    child: dict[str, Any],
    relationship_type: str,
    parent_facts: list[dict[str, Any]],
    child_facts: list[dict[str, Any]],
) -> list[Violation]:
    """Validates biological and chronological plausibility of a parent-child relationship."""
    violations: list[Violation] = []
    parent_pid = parent["pid"]
    child_pid = child["pid"]

    p_events = _extract_primary_facts(parent, parent_facts)
    c_events = _extract_primary_facts(child, child_facts)

    p_birth = p_events["birth"]
    p_death = p_events["death"]
    c_birth = c_events["birth"]

    if not p_birth or not c_birth:
        return violations

    age_at_child_birth = calculate_age_in_years(p_birth, c_birth)
    if age_at_child_birth is None:
        return violations

    gender = (parent.get("gender") or "").strip().lower()
    is_female = gender.startswith("f") or relationship_type == "mother"
    is_male = (gender.startswith("m") and not is_female) or relationship_type == "father"

    # Rule 1: Relational Inversion (Child born before parent)
    if age_at_child_birth <= 0:
        violations.append(
            Violation(
                rule_id="REL-INVERSION",
                severity="ERROR",
                person_pid=child_pid,
                relative_pid=parent_pid,
                description=(
                    f"Child born before or in same year as parent "
                    f"(Child Birth: {c_birth}, Parent Birth: {p_birth}, Age Diff: {age_at_child_birth:.1f} yrs)"
                ),
                details={
                    "child_birth": str(c_birth),
                    "parent_birth": str(p_birth),
                    "age_at_child_birth": age_at_child_birth,
                },
            )
        )
        return violations

    # Rule 2: Mother Biological Constraints
    if is_female:
        # Mother age limits: 13 to 50
        if age_at_child_birth < 13.0:
            violations.append(
                Violation(
                    rule_id="BIO-MOTH-AGE",
                    severity="ERROR",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Mother was only {age_at_child_birth:.1f} years old at child's birth "
                        f"(below minimum biological threshold of 13)"
                    ),
                    details={
                        "mother_birth": str(p_birth),
                        "child_birth": str(c_birth),
                        "mother_age": age_at_child_birth,
                    },
                )
            )
        elif age_at_child_birth > 50.0:
            violations.append(
                Violation(
                    rule_id="BIO-MOTH-AGE",
                    severity="ERROR",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Mother was {age_at_child_birth:.1f} years old at child's birth "
                        f"(exceeds maximum biological threshold of 50)"
                    ),
                    details={
                        "mother_birth": str(p_birth),
                        "child_birth": str(c_birth),
                        "mother_age": age_at_child_birth,
                    },
                )
            )
        elif age_at_child_birth < 15.0:
            violations.append(
                Violation(
                    rule_id="BIO-MOTH-AGE",
                    severity="WARNING",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Young maternal age: Mother was {age_at_child_birth:.1f} years old at child's birth"
                    ),
                    details={"mother_age": age_at_child_birth},
                )
            )
        elif age_at_child_birth >= 46.0:
            violations.append(
                Violation(
                    rule_id="BIO-MOTH-AGE",
                    severity="WARNING",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Advanced maternal age: Mother was {age_at_child_birth:.1f} years old at child's birth"
                    ),
                    details={"mother_age": age_at_child_birth},
                )
            )

        # Mother Posthumous check: Child born after mother's death
        if p_death:
            if p_death.exact_date and c_birth.exact_date:
                days_after_death = (c_birth.exact_date - p_death.exact_date).days
                if days_after_death > 0:
                    violations.append(
                        Violation(
                            rule_id="BIO-MOTH-POSTHUMOUS",
                            severity="ERROR",
                            person_pid=child_pid,
                            relative_pid=parent_pid,
                            description=(
                                f"Child born {days_after_death} days after mother's death "
                                f"(Mother Death: {p_death}, Child Birth: {c_birth})"
                            ),
                            details={
                                "mother_death": str(p_death),
                                "child_birth": str(c_birth),
                                "days_after_death": days_after_death,
                            },
                        )
                    )
            elif p_death.year is not None and c_birth.year is not None:
                if c_birth.year > p_death.year or (
                    c_birth.year == p_death.year
                    and c_birth.month is not None
                    and p_death.month is not None
                    and c_birth.month > p_death.month
                ):
                    violations.append(
                        Violation(
                            rule_id="BIO-MOTH-POSTHUMOUS",
                            severity="ERROR",
                            person_pid=child_pid,
                            relative_pid=parent_pid,
                            description=(
                                f"Child born after mother's death "
                                f"(Mother Death: {p_death}, Child Birth: {c_birth})"
                            ),
                            details={"mother_death": str(p_death), "child_birth": str(c_birth)},
                        )
                    )

    # Rule 3: Father Biological Constraints
    elif is_male:
        # Father age limits: 14 to 85
        if age_at_child_birth < 14.0:
            violations.append(
                Violation(
                    rule_id="BIO-FATH-AGE",
                    severity="ERROR",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Father was only {age_at_child_birth:.1f} years old at child's conception/birth "
                        f"(below minimum biological threshold of 14)"
                    ),
                    details={
                        "father_birth": str(p_birth),
                        "child_birth": str(c_birth),
                        "father_age": age_at_child_birth,
                    },
                )
            )
        elif age_at_child_birth > 85.0:
            violations.append(
                Violation(
                    rule_id="BIO-FATH-AGE",
                    severity="ERROR",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Father was {age_at_child_birth:.1f} years old at child's birth "
                        f"(exceeds biological plausibility threshold of 85)"
                    ),
                    details={
                        "father_birth": str(p_birth),
                        "child_birth": str(c_birth),
                        "father_age": age_at_child_birth,
                    },
                )
            )
        elif age_at_child_birth < 16.0:
            violations.append(
                Violation(
                    rule_id="BIO-FATH-AGE",
                    severity="WARNING",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Young paternal age: Father was {age_at_child_birth:.1f} years old at child's birth"
                    ),
                    details={"father_age": age_at_child_birth},
                )
            )
        elif age_at_child_birth >= 70.0:
            violations.append(
                Violation(
                    rule_id="BIO-FATH-AGE",
                    severity="WARNING",
                    person_pid=child_pid,
                    relative_pid=parent_pid,
                    description=(
                        f"Advanced paternal age: Father was {age_at_child_birth:.1f} years old at child's birth"
                    ),
                    details={"father_age": age_at_child_birth},
                )
            )

        # Father Posthumous check: Child born > 280 days after father's death
        if p_death:
            if p_death.exact_date and c_birth.exact_date:
                days_after_death = (c_birth.exact_date - p_death.exact_date).days
                if days_after_death > 280:  # ~9.5 months gestation limit
                    violations.append(
                        Violation(
                            rule_id="BIO-FATH-POSTHUMOUS",
                            severity="ERROR",
                            person_pid=child_pid,
                            relative_pid=parent_pid,
                            description=(
                                f"Child born {days_after_death} days (> 280 days) after father's death "
                                f"(Father Death: {p_death}, Child Birth: {c_birth})"
                            ),
                            details={
                                "father_death": str(p_death),
                                "child_birth": str(c_birth),
                                "days_after_death": days_after_death,
                            },
                        )
                    )
                elif days_after_death > 0:
                    violations.append(
                        Violation(
                            rule_id="BIO-FATH-POSTHUMOUS",
                            severity="INFO",
                            person_pid=child_pid,
                            relative_pid=parent_pid,
                            description=(
                                f"Posthumous birth: Child born {days_after_death} days after father's death "
                                f"(within normal human gestation window)"
                            ),
                            details={
                                "father_death": str(p_death),
                                "child_birth": str(c_birth),
                                "days_after_death": days_after_death,
                            },
                        )
                    )
            elif p_death.year is not None and c_birth.year is not None:
                if c_birth.year > p_death.year + 1:
                    violations.append(
                        Violation(
                            rule_id="BIO-FATH-POSTHUMOUS",
                            severity="ERROR",
                            person_pid=child_pid,
                            relative_pid=parent_pid,
                            description=(
                                f"Child born after father's death by over a calendar year "
                                f"(Father Death: {p_death}, Child Birth: {c_birth})"
                            ),
                            details={"father_death": str(p_death), "child_birth": str(c_birth)},
                        )
                    )

    return violations


def check_spousal_chronology(
    husband: dict[str, Any],
    wife: dict[str, Any],
    marriage_fact: Optional[dict[str, Any]],
    husband_facts: list[dict[str, Any]],
    wife_facts: list[dict[str, Any]],
) -> list[Violation]:
    """Validates marriage ages and spousal chronology."""
    violations: list[Violation] = []
    if not marriage_fact:
        return violations

    m_date = parse_date(
        date_formal=marriage_fact.get("date_formal"),
        date_original=marriage_fact.get("date_original"),
    )
    if not m_date:
        return violations

    h_events = _extract_primary_facts(husband, husband_facts)
    w_events = _extract_primary_facts(wife, wife_facts)

    # Husband marriage age
    if h_events["birth"]:
        h_age = calculate_age_in_years(h_events["birth"], m_date)
        if h_age is not None:
            if h_age < 12.0:
                violations.append(
                    Violation(
                        rule_id="CHRONO-MARR-AGE",
                        severity="ERROR",
                        person_pid=husband["pid"],
                        relative_pid=wife["pid"],
                        description=(
                            f"Husband was only {h_age:.1f} years old at marriage "
                            f"(Marriage: {m_date}, Birth: {h_events['birth']})"
                        ),
                        details={"marriage_age": h_age, "spouse_pid": wife["pid"]},
                    )
                )
            elif h_age < 15.0:
                violations.append(
                    Violation(
                        rule_id="CHRONO-MARR-AGE",
                        severity="WARNING",
                        person_pid=husband["pid"],
                        relative_pid=wife["pid"],
                        description=(
                            f"Husband was young ({h_age:.1f} years old) at marriage"
                        ),
                        details={"marriage_age": h_age, "spouse_pid": wife["pid"]},
                    )
                )

    # Wife marriage age
    if w_events["birth"]:
        w_age = calculate_age_in_years(w_events["birth"], m_date)
        if w_age is not None:
            if w_age < 12.0:
                violations.append(
                    Violation(
                        rule_id="CHRONO-MARR-AGE",
                        severity="ERROR",
                        person_pid=wife["pid"],
                        relative_pid=husband["pid"],
                        description=(
                            f"Wife was only {w_age:.1f} years old at marriage "
                            f"(Marriage: {m_date}, Birth: {w_events['birth']})"
                        ),
                        details={"marriage_age": w_age, "spouse_pid": husband["pid"]},
                    )
                )
            elif w_age < 14.0:
                violations.append(
                    Violation(
                        rule_id="CHRONO-MARR-AGE",
                        severity="WARNING",
                        person_pid=wife["pid"],
                        relative_pid=husband["pid"],
                        description=(
                            f"Wife was young ({w_age:.1f} years old) at marriage"
                        ),
                        details={"marriage_age": w_age, "spouse_pid": husband["pid"]},
                    )
                )

    # Marriage after death
    if h_events["death"]:
        days = calculate_days_between(h_events["death"], m_date)
        if days is not None and days > 0:
            violations.append(
                Violation(
                    rule_id="CHRONO-EVENT-ORDER",
                    severity="ERROR",
                    person_pid=husband["pid"],
                    relative_pid=wife["pid"],
                    description=f"Marriage occurs after husband's death (Husband Death: {h_events['death']}, Marriage: {m_date})",
                    details={"marriage_date": str(m_date), "death_date": str(h_events["death"])},
                )
            )

    if w_events["death"]:
        days = calculate_days_between(w_events["death"], m_date)
        if days is not None and days > 0:
            violations.append(
                Violation(
                    rule_id="CHRONO-EVENT-ORDER",
                    severity="ERROR",
                    person_pid=wife["pid"],
                    relative_pid=husband["pid"],
                    description=f"Marriage occurs after wife's death (Wife Death: {w_events['death']}, Marriage: {m_date})",
                    details={"marriage_date": str(m_date), "death_date": str(w_events["death"])},
                )
            )

    return violations
