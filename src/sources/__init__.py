"""Multi-source external record harvesters and candidate discovery engine."""

from src.sources.base import BaseHarvester, CandidateDiscovery, score_candidate
from src.sources.chronicling_america import ChroniclingAmericaHarvester
from src.sources.internet_archive import InternetArchiveHarvester

__all__ = [
    "BaseHarvester",
    "CandidateDiscovery",
    "score_candidate",
    "ChroniclingAmericaHarvester",
    "InternetArchiveHarvester",
]
