"""Pedigree package for extracting and ingesting FamilySearch ancestry trees."""

from src.pedigree.extractor import extract_facts, extract_person, extract_relationships
from src.pedigree.ingest import IngestionResult, PedigreeIngester

__all__ = [
    "extract_person",
    "extract_facts",
    "extract_relationships",
    "PedigreeIngester",
    "IngestionResult",
]
