"""GEDCOM 5.5.1 Lineage-Linked Exporter for Genealogical Knowledge Graph."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.storage.db import Database


def clean_gedcom_text(text: str | None) -> str:
    """Sanitizes text for GEDCOM compliance by removing invalid characters and newlines."""
    if not text:
        return ""
    # Replace newlines with spaces and strip illegal non-printable ASCII
    clean = re.sub(r"[\r\n\t]+", " ", str(text))
    clean = re.sub(r"[^\x20-\x7E\xA0-\xFF]", "", clean)
    return clean.strip()


def format_gedcom_name(name: str | None) -> tuple[str, str, str, str]:
    """Splits full name into GEDCOM 1 NAME, GIVN, SURN, and NSFX components.

    Example:
        'Douglas Paul Smith Jr' -> ('Douglas Paul /Smith/ Jr', 'Douglas Paul', 'Smith', 'Jr')
    """
    if not name or not name.strip():
        return "Unknown //", "Unknown", "", ""

    tokens = clean_gedcom_text(name).split()
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
    suffix = ""
    if len(tokens) > 1 and tokens[-1].lower() in suffixes:
        suffix = tokens.pop()

    if len(tokens) == 0:
        return "Unknown //", "Unknown", "", ""
    elif len(tokens) == 1:
        surname = tokens[0]
        return f"/{surname}/", "", surname, suffix
    else:
        surname = tokens[-1]
        given = " ".join(tokens[:-1])
        suffix_part = f" {suffix}" if suffix else ""
        full_line = f"{given} /{surname}/{suffix_part}"
        return full_line, given, surname, suffix


def clean_pointer_id(raw_id: str, prefix: str = "I") -> str:
    """Formats an identifier into a valid GEDCOM cross-reference pointer."""
    clean = re.sub(r"[^A-Za-z0-9_]", "_", str(raw_id))
    return f"@{prefix}_{clean}@"


FACT_TYPE_MAP = {
    "birth": "BIRT",
    "death": "DEAT",
    "burial": "BURI",
    "christening": "CHR",
    "baptism": "BAPM",
    "marriage": "MARR",
    "residence": "RESI",
    "occupation": "OCCU",
    "immigration": "IMMI",
    "emigration": "EMIG",
    "naturalization": "NATU",
    "military": "_MILT",
    "military service": "_MILT",
}


class GedcomExporter:
    """Generates standard GEDCOM 5.5.1 Lineage-Linked files from SQLite database."""

    def __init__(self, db: Database | None = None, db_path: str | Path = "data/pedigree.sqlite") -> None:
        self.db = db or Database(db_path)

    def export_to_file(
        self,
        output_path: str | Path,
        max_generation: int | None = None,
        direct_only: bool = False,
        include_sources: bool = True,
    ) -> dict[str, int]:
        """Exports pedigree tree to a GEDCOM 5.5.1 text file.

        Returns:
            Dictionary with counts: {'individuals': N, 'families': N, 'sources': N}
        """
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        content, stats = self.export_to_string(
            max_generation=max_generation,
            direct_only=direct_only,
            include_sources=include_sources,
        )

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content)

        return stats

    def export_to_string(
        self,
        max_generation: int | None = None,
        direct_only: bool = False,
        include_sources: bool = True,
    ) -> tuple[str, dict[str, int]]:
        """Generates GEDCOM 5.5.1 string from database."""
        with self.db.get_connection() as conn:
            # 1. Select individuals
            person_query = """
            SELECT p.*, pt.generation, pt.ascendancy_number
            FROM persons p
            LEFT JOIN pedigree_tree pt ON p.pid = pt.person_pid
            WHERE 1=1
            """
            params: list[Any] = []
            if max_generation is not None:
                person_query += " AND pt.generation <= ?"
                params.append(max_generation)
            if direct_only:
                person_query += " AND pt.ascendancy_number IS NOT NULL"

            person_query += " ORDER BY pt.generation ASC, pt.ascendancy_number ASC, p.pid ASC"
            persons = [dict(r) for r in conn.execute(person_query, params).fetchall()]
            valid_pids = {p["pid"] for p in persons}

            # 2. Select facts for valid individuals
            facts_by_pid: dict[str, list[dict[str, Any]]] = {}
            if valid_pids:
                # Batch fetch facts
                for f in conn.execute("SELECT * FROM facts").fetchall():
                    pid = f["person_pid"]
                    if pid in valid_pids:
                        facts_by_pid.setdefault(pid, []).append(dict(f))

            # 3. Select relationships
            parent_child_rels = conn.execute(
                "SELECT parent_pid, child_pid FROM relationships WHERE rel_type = 'parent-child'"
            ).fetchall()
            couple_rels = conn.execute(
                "SELECT spouse1_pid, spouse2_pid FROM relationships WHERE rel_type = 'couple'"
            ).fetchall()

            # 4. Select sources & person_sources
            sources_by_id = {}
            person_source_links: dict[str, list[str]] = {}
            if include_sources:
                for s in conn.execute("SELECT * FROM sources").fetchall():
                    sources_by_id[s["id"]] = dict(s)
                for ps in conn.execute("SELECT person_pid, source_id FROM person_sources").fetchall():
                    if ps["person_pid"] in valid_pids and ps["source_id"] in sources_by_id:
                        person_source_links.setdefault(ps["person_pid"], []).append(ps["source_id"])

        # Build family structures
        # Map: child_pid -> list of parent_pids
        parents_by_child: dict[str, list[str]] = {}
        for r in parent_child_rels:
            parent_pid = r["parent_pid"]
            child_pid = r["child_pid"]
            if parent_pid in valid_pids and child_pid in valid_pids:
                parents_by_child.setdefault(child_pid, []).append(parent_pid)

        # Map person gender
        gender_by_pid = {p["pid"]: (p.get("gender") or "Unknown").upper() for p in persons}

        # Build unique families: Key = (husb_pid, wife_pid)
        families: dict[tuple[str | None, str | None], dict[str, Any]] = {}
        child_to_fam: dict[str, str] = {}
        spouse_to_fams: dict[str, list[str]] = {}
        fam_counter = 1

        def get_or_create_fam(parent1: str | None, parent2: str | None) -> str:
            nonlocal fam_counter
            # Determine husband and wife by gender if possible
            husb = None
            wife = None
            if parent1 and parent2:
                g1 = gender_by_pid.get(parent1, "UNKNOWN")
                g2 = gender_by_pid.get(parent2, "UNKNOWN")
                if g1 == "MALE" or g2 == "FEMALE":
                    husb, wife = parent1, parent2
                elif g1 == "FEMALE" or g2 == "MALE":
                    husb, wife = parent2, parent1
                else:
                    sorted_p = sorted([parent1, parent2])
                    husb, wife = sorted_p[0], sorted_p[1]
            elif parent1:
                g1 = gender_by_pid.get(parent1, "UNKNOWN")
                if g1 == "FEMALE":
                    wife = parent1
                else:
                    husb = parent1
            elif parent2:
                g2 = gender_by_pid.get(parent2, "UNKNOWN")
                if g2 == "FEMALE":
                    wife = parent2
                else:
                    husb = parent2

            key = (husb, wife)
            if key in families:
                return families[key]["id"]

            fam_id = f"@F{fam_counter}@"
            fam_counter += 1
            families[key] = {
                "id": fam_id,
                "husb": husb,
                "wife": wife,
                "children": [],
            }
            if husb:
                spouse_to_fams.setdefault(husb, []).append(fam_id)
            if wife:
                spouse_to_fams.setdefault(wife, []).append(fam_id)
            return fam_id

        # 1. Populate families from parent-child links
        for child_pid, parent_list in parents_by_child.items():
            if len(parent_list) >= 2:
                fam_id = get_or_create_fam(parent_list[0], parent_list[1])
            elif len(parent_list) == 1:
                fam_id = get_or_create_fam(parent_list[0], None)
            else:
                continue

            child_to_fam[child_pid] = fam_id
            key = None
            for k, f_data in families.items():
                if f_data["id"] == fam_id:
                    key = k
                    break
            if key and child_pid not in families[key]["children"]:
                families[key]["children"].append(child_pid)

        # 2. Add couples who might not have children in the exported subset
        for r in couple_rels:
            sp1 = r["spouse1_pid"]
            sp2 = r["spouse2_pid"]
            if sp1 in valid_pids and sp2 in valid_pids:
                get_or_create_fam(sp1, sp2)

        # Construct GEDCOM lines
        lines: list[str] = []

        # --- Header ---
        now_dt = datetime.now(timezone.utc)
        date_str = now_dt.strftime("%d %b %Y").upper()
        time_str = now_dt.strftime("%H:%M:%S")

        lines.append("0 HEAD")
        lines.append("1 SOUR ANCESTRY_GENEALOGY")
        lines.append("2 VERS 0.8.0")
        lines.append("2 NAME Ancestry Genealogy Knowledge Graph")
        lines.append("1 DEST ANY")
        lines.append(f"1 DATE {date_str}")
        lines.append(f"2 TIME {time_str}")
        lines.append("1 GEDC")
        lines.append("2 VERS 5.5.1")
        lines.append("2 FORM LINEAGE-LINKED")
        lines.append("1 CHAR UTF-8")

        # --- Individuals ---
        used_source_ids: set[str] = set()

        for p in persons:
            pid = p["pid"]
            indi_ptr = clean_pointer_id(pid, prefix="I")
            lines.append(f"0 {indi_ptr} INDI")

            # Name
            name_line, givn, surn, nsfx = format_gedcom_name(p.get("name"))
            lines.append(f"1 NAME {name_line}")
            if givn:
                lines.append(f"2 GIVN {givn}")
            if surn:
                lines.append(f"2 SURN {surn}")
            if nsfx:
                lines.append(f"2 NSFX {nsfx}")

            # Sex
            gender = (p.get("gender") or "Unknown").upper()
            if gender == "MALE":
                lines.append("1 SEX M")
            elif gender == "FEMALE":
                lines.append("1 SEX F")
            else:
                lines.append("1 SEX U")

            # Events / Facts
            p_facts = facts_by_pid.get(pid, [])
            emitted_events: set[str] = set()

            for f in p_facts:
                ftype = (f.get("fact_type") or "").strip().lower()
                tag = FACT_TYPE_MAP.get(ftype)
                if not tag:
                    tag = "EVEN"

                # Avoid duplicate birth or death if already emitted
                if tag in ("BIRT", "DEAT") and tag in emitted_events:
                    continue

                emitted_events.add(tag)
                lines.append(f"1 {tag}")
                if tag == "EVEN" and f.get("fact_type"):
                    lines.append(f"2 TYPE {clean_gedcom_text(f['fact_type'])}")

                date_val = f.get("date_original") or f.get("date_formal")
                if date_val:
                    lines.append(f"2 DATE {clean_gedcom_text(date_val)}")

                place_val = f.get("place_normalized") or f.get("place_original")
                if place_val:
                    lines.append(f"2 PLAC {clean_gedcom_text(place_val)}")

                if f.get("value"):
                    lines.append(f"2 NOTE {clean_gedcom_text(f['value'])}")

            # Fallback birth and death from persons table if not in facts
            if "BIRT" not in emitted_events and (p.get("birth_date") or p.get("birth_place")):
                lines.append("1 BIRT")
                if p.get("birth_date"):
                    lines.append(f"2 DATE {clean_gedcom_text(p['birth_date'])}")
                if p.get("birth_place"):
                    lines.append(f"2 PLAC {clean_gedcom_text(p['birth_place'])}")

            if "DEAT" not in emitted_events and p.get("living") != 1 and (p.get("death_date") or p.get("death_place")):
                lines.append("1 DEAT")
                if p.get("death_date"):
                    lines.append(f"2 DATE {clean_gedcom_text(p['death_date'])}")
                if p.get("death_place"):
                    lines.append(f"2 PLAC {clean_gedcom_text(p['death_place'])}")

            # Family links
            if pid in child_to_fam:
                lines.append(f"1 FAMC {child_to_fam[pid]}")

            for f_id in spouse_to_fams.get(pid, []):
                lines.append(f"1 FAMS {f_id}")

            # Sources
            if include_sources:
                for sid in person_source_links.get(pid, []):
                    s_ptr = clean_pointer_id(sid, prefix="S")
                    lines.append(f"1 SOUR {s_ptr}")
                    used_source_ids.add(sid)

            # Metadata Note
            if p.get("generation") is not None:
                lines.append(f"1 NOTE Generation {p['generation']}, Ahnentafel {p.get('ascendancy_number') or '-'}")

        # --- Families ---
        for fam_key, fam_data in families.items():
            lines.append(f"0 {fam_data['id']} FAM")
            if fam_data["husb"]:
                lines.append(f"1 HUSB {clean_pointer_id(fam_data['husb'], prefix='I')}")
            if fam_data["wife"]:
                lines.append(f"1 WIFE {clean_pointer_id(fam_data['wife'], prefix='I')}")
            for c_pid in fam_data["children"]:
                lines.append(f"1 CHIL {clean_pointer_id(c_pid, prefix='I')}")

        # --- Sources ---
        if include_sources:
            for sid in sorted(used_source_ids):
                s_data = sources_by_id.get(sid)
                if not s_data:
                    continue
                s_ptr = clean_pointer_id(sid, prefix="S")
                lines.append(f"0 {s_ptr} SOUR")
                title = clean_gedcom_text(s_data.get("title") or "Historical Source Citation")
                lines.append(f"1 TITL {title}")
                if s_data.get("collection_url"):
                    lines.append(f"1 REPO {clean_gedcom_text(s_data['collection_url'])}")
                if s_data.get("about_url"):
                    lines.append(f"1 NOTE URL: {clean_gedcom_text(s_data['about_url'])}")
                if s_data.get("citation_text"):
                    lines.append(f"1 NOTE Citation: {clean_gedcom_text(s_data['citation_text'])}")

        # --- Trailer ---
        lines.append("0 TRLR")

        content = "\n".join(lines) + "\n"
        stats = {
            "individuals": len(persons),
            "families": len(families),
            "sources": len(used_source_ids),
        }
        return content, stats
