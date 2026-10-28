"""Source and evidence classifier implementing the Genealogical Proof Standard (GPS)."""

import re
from typing import Any


class SourceClassifier:
    """Classifies genealogical sources into evidence tiers and record types."""

    # Patterns for Tier 3: Unverified / User assertions / Member trees
    TIER3_PATTERNS = [
        (r"pedigree resource file", "user_tree"),
        (r"ancestry family tree", "user_tree"),
        (r"family tree", "user_tree"),
        (r"legacy nfs source", "user_tree"),
        (r"one world tree", "user_tree"),
        (r"millennium file", "user_tree"),
        (r"geneanet community tree", "user_tree"),
        (r"user submission", "user_tree"),
    ]

    # Patterns for Tier 1: Contemporary Primary Documentary Evidence
    TIER1_PATTERNS = [
        # Censuses
        (r"\b\d{4}\s+census\b", "census"),
        (r"\bcensus\b", "census"),
        # Vital - Birth & Baptism
        (r"\bbirth\s+index\b", "vital_birth"),
        (r"\bbirth\s+certificate\b", "vital_birth"),
        (r"\bbirths\s+and\s+christenings\b", "vital_birth"),
        (r"\bbaptism\b", "vital_birth"),
        (r"\bchristening\b", "vital_birth"),
        (r"\bparish\s+registers?\b", "parish_register"),
        (r"\bparish\s+records?\b", "parish_register"),
        (r"\bchurch\s+records?\b", "parish_register"),
        (r"\bkirk\s+session\b", "parish_register"),
        # Vital - Marriage
        (r"\bmarriage\s+index\b", "vital_marriage"),
        (r"\bmarriage\s+certificate\b", "vital_marriage"),
        (r"\bmarriages\b", "vital_marriage"),
        (r"\bmarriage\s+records?\b", "vital_marriage"),
        (r"\bmarriage\s+license\b", "vital_marriage"),
        (r"\bbanns\b", "vital_marriage"),
        (r"\bmarriage\s+allegation\b", "vital_marriage"),
        (r"\bmarriage\s+bond\b", "vital_marriage"),
        # Vital - Death & Cemetery
        (r"\bdeath\s+index\b", "vital_death"),
        (r"\bdeath\s+certificate\b", "vital_death"),
        (r"\bdeaths\s+and\s+burials\b", "vital_death"),
        (r"\bburial\b", "vital_death"),
        (r"\bfind\s+a\s+grave\b", "vital_death"),
        (r"\bbilliongraves\b", "vital_death"),
        (r"\bcemetery\b", "vital_death"),
        (r"\binterment\b", "vital_death"),
        # Military
        (r"\bdraft\s+registration\b", "military"),
        (r"\bmilitary\b", "military"),
        (r"\benlistment\b", "military"),
        (r"\bveteran\b", "military"),
        (r"\bcivil\s+war\b", "military"),
        (r"\bworld\s+war\b", "military"),
        (r"\bpension\b", "military"),
        # Social Security
        (r"\bnumident\b", "social_security"),
        (r"\bsocial\s+security\b", "social_security"),
        (r"\bssdi\b", "social_security"),
        # Probate, Inquisitions & Legal Records
        (r"\bprobate\b", "probate"),
        (r"\bwill\s+and\s+probate\b", "probate"),
        (r"\bestate\s+files\b", "probate"),
        (r"\bdeed\b", "probate"),
        (r"\bland\s+grant\b", "probate"),
        (r"\binquisition\s+post\s+mortem\b", "probate"),
        (r"\bipm\b", "probate"),
        (r"\bprerogative\s+court\b", "probate"),
        (r"\btestament\s+dative\b", "probate"),
        (r"\btestament\s+testamentar\b", "probate"),
        (r"\bfeet\s+of\s+fines\b", "probate"),
        (r"\bcourt\s+rolls?\b", "probate"),
        (r"\bmanorial\b", "probate"),
        (r"\bchancery\b", "probate"),
    ]

    # Patterns for Tier 2: Secondary / Derivative Evidence
    TIER2_PATTERNS = [
        # Heralds' Visitations & Pedigrees
        (r"\bvisitations?\s+of\b", "heraldic_visitation"),
        (r"\bheraldic\s+visitation\b", "heraldic_visitation"),
        (r"\bheraldic\b", "heraldic_visitation"),
        (r"\bpedigrees\s+of\b", "heraldic_visitation"),
        (r"\bvisitation\s+pedigree\b", "heraldic_visitation"),
        # Peerages & Nobility Compilations
        (r"\bpeerage\b", "peerage"),
        (r"\bbaronetage\b", "peerage"),
        (r"\bcokayne\b", "peerage"),
        (r"\bburke'?s\b", "peerage"),
        (r"\blanded\s+gentry\b", "peerage"),
        # Academic & Scholarly Registers
        (r"\balumni\s+cantabrigienses\b", "secondary"),
        (r"\balumni\s+oxonienses\b", "secondary"),
        (r"\bcounty\s+history\b", "secondary"),
        (r"\bhistory\s+and\s+antiquities\b", "secondary"),
        # Modern Secondary Compilations & Newspapers
        (r"\bobituary\b", "secondary"),
        (r"\bnewspaper\b", "secondary"),
        (r"\bpassenger\s+list\b", "secondary"),
        (r"\bmanifest\b", "secondary"),
        (r"\bimmigration\b", "secondary"),
        (r"\bnaturalization\b", "secondary"),
        (r"\bhistory\s+of\b", "secondary"),
        (r"\bbiographical\b", "secondary"),
        (r"\bdirectory\b", "secondary"),
        (r"\bcity\s+directory\b", "secondary"),
    ]

    @classmethod
    def classify(cls, source: dict[str, Any]) -> tuple[int, str]:
        """Classifies a source dictionary into (tier, record_type).

        Returns:
            tuple of (tier: int, record_type: str)
            - Tier 1: Primary Contemporary Documentary Record
            - Tier 2: Secondary / Derivative Evidence
            - Tier 3: Unverified Assertion / User-submitted Tree
        """
        title = (source.get("title") or "").lower()
        citation = (source.get("citation_text") or "").lower()
        about = (source.get("about_url") or "").lower()

        combined_text = f"{title} {citation} {about}"

        # Check Tier 3 (User trees, unverified claims) first
        for pattern, rec_type in cls.TIER3_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return 3, rec_type

        # Check Tier 1 (Primary documentary records)
        for pattern, rec_type in cls.TIER1_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return 1, rec_type

        # Check Tier 2 (Secondary / Derivative records)
        for pattern, rec_type in cls.TIER2_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return 2, rec_type

        # Fallback heuristic:
        # If it points to an official FamilySearch ARK link (/ark:/61903/), it's at least Tier 2 archival record
        if "ark:/61903/" in about:
            return 2, "archival_record"

        # Otherwise unverified / user note
        return 3, "other"


def classify_source(source: dict[str, Any]) -> tuple[int, str]:
    """Helper wrapper function to classify a source."""
    return SourceClassifier.classify(source)
