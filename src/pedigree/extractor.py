"""Extractor to normalize GEDCOM X payloads into relational models."""

import math
from typing import Any


def extract_person(raw_person: dict[str, Any]) -> dict[str, Any]:
    """Extracts a normalized person dictionary from a FamilySearch GEDCOM X person payload."""
    pid = raw_person.get("id", "")
    display = raw_person.get("display", {})

    # Name extraction
    name = display.get("name")
    if not name and "names" in raw_person and raw_person["names"]:
        name_forms = raw_person["names"][0].get("nameForms", [])
        if name_forms:
            name = name_forms[0].get("fullText")

    # Gender extraction
    gender = display.get("gender")
    if not gender and "gender" in raw_person:
        gender_type = raw_person["gender"].get("type", "")
        if "Male" in gender_type:
            gender = "Male"
        elif "Female" in gender_type:
            gender = "Female"
        else:
            gender = "Unknown"

    lifespan = display.get("lifespan")
    living = raw_person.get("living", False)

    birth_date = display.get("birthDate")
    birth_place = display.get("birthPlace")
    death_date = display.get("deathDate")
    death_place = display.get("deathPlace")

    # Fallback to facts list if display is missing details
    facts = raw_person.get("facts", [])
    for fact in facts:
        fact_type = fact.get("type", "")
        if "Birth" in fact_type and not birth_date:
            date_info = fact.get("date", {})
            birth_date = date_info.get("original") or date_info.get("formal")
            place_info = fact.get("place", {})
            birth_place = place_info.get("original")
        elif "Death" in fact_type and not death_date:
            date_info = fact.get("date", {})
            death_date = date_info.get("original") or date_info.get("formal")
            place_info = fact.get("place", {})
            death_place = place_info.get("original")

    return {
        "pid": pid,
        "name": name or "Unknown",
        "gender": gender or "Unknown",
        "lifespan": lifespan or "",
        "living": bool(living),
        "birth_date": birth_date or "",
        "birth_place": birth_place or "",
        "death_date": death_date or "",
        "death_place": death_place or "",
        "raw_json": raw_person,
    }


def extract_facts(raw_person: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts granular facts (vital events, residence, etc.) for a person."""
    extracted = []
    pid = raw_person.get("id", "")
    facts = raw_person.get("facts", [])

    for f in facts:
        fact_type = f.get("type", "")
        # Clean type identifier (e.g. http://gedcomx.org/Birth -> Birth)
        clean_type = fact_type.split("/")[-1] if "/" in fact_type else fact_type

        date_info = f.get("date", {})
        date_orig = date_info.get("original")
        date_formal = date_info.get("formal")

        place_info = f.get("place", {})
        place_orig = place_info.get("original")
        if isinstance(place_orig, (dict, list)):
            place_orig = json.dumps(place_orig)
        elif place_orig is not None:
            place_orig = str(place_orig)

        place_norm = place_info.get("normalized")
        if isinstance(place_norm, list):
            place_norm = ", ".join(
                item.get("value", str(item)) if isinstance(item, dict) else str(item)
                for item in place_norm
            )
        elif isinstance(place_norm, dict):
            place_norm = place_norm.get("value", str(place_norm))
        elif place_norm is not None:
            place_norm = str(place_norm)

        val = f.get("value")
        if isinstance(val, (dict, list)):
            val = json.dumps(val)
        elif val is not None:
            val = str(val)

        extracted.append(
            {
                "person_pid": pid,
                "fact_type": clean_type,
                "date_original": str(date_orig) if date_orig is not None else None,
                "date_formal": str(date_formal) if date_formal is not None else None,
                "place_original": place_orig,
                "place_normalized": place_norm,
                "value": val,
                "raw_json": f,
            }
        )

    return extracted


def extract_relationships(
    relationships_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extracts binary parent-child and couple relationships from FamilySearch relationships or childAndParents."""
    extracted = []

    for rel in relationships_data:
        rel_id = rel.get("id")
        rel_type = rel.get("type", "")

        # Standard GEDCOM X Relationship (Couple, ParentChild)
        if "Couple" in rel_type:
            p1 = rel.get("person1", {}).get("resourceId")
            p2 = rel.get("person2", {}).get("resourceId")
            if p1 and p2:
                extracted.append(
                    {
                        "id": rel_id or f"couple_{min(p1, p2)}_{max(p1, p2)}",
                        "rel_type": "couple",
                        "parent_pid": None,
                        "child_pid": None,
                        "spouse1_pid": p1,
                        "spouse2_pid": p2,
                        "lineage_type": None,
                        "raw_json": rel,
                    }
                )
        elif "ParentChild" in rel_type:
            parent = rel.get("person1", {}).get("resourceId")
            child = rel.get("person2", {}).get("resourceId")
            if parent and child:
                extracted.append(
                    {
                        "id": rel_id or f"pc_{parent}_{child}",
                        "rel_type": "parent-child",
                        "parent_pid": parent,
                        "child_pid": child,
                        "spouse1_pid": None,
                        "spouse2_pid": None,
                        "lineage_type": "biological",
                        "raw_json": rel,
                    }
                )
        else:
            # Handle childAndParentsRelationships format
            child_res = rel.get("child", {}).get("resourceId")
            father_res = rel.get("father", {}).get("resourceId")
            mother_res = rel.get("mother", {}).get("resourceId")

            if child_res and father_res:
                extracted.append(
                    {
                        "id": f"{rel_id}_father" if rel_id else f"pc_{father_res}_{child_res}",
                        "rel_type": "parent-child",
                        "parent_pid": father_res,
                        "child_pid": child_res,
                        "spouse1_pid": None,
                        "spouse2_pid": None,
                        "lineage_type": "biological",
                        "raw_json": rel,
                    }
                )

            if child_res and mother_res:
                extracted.append(
                    {
                        "id": f"{rel_id}_mother" if rel_id else f"pc_{mother_res}_{child_res}",
                        "rel_type": "parent-child",
                        "parent_pid": mother_res,
                        "child_pid": child_res,
                        "spouse1_pid": None,
                        "spouse2_pid": None,
                        "lineage_type": "biological",
                        "raw_json": rel,
                    }
                )

            if father_res and mother_res:
                couple_id = f"couple_{min(father_res, mother_res)}_{max(father_res, mother_res)}"
                extracted.append(
                    {
                        "id": couple_id,
                        "rel_type": "couple",
                        "parent_pid": None,
                        "child_pid": None,
                        "spouse1_pid": father_res,
                        "spouse2_pid": mother_res,
                        "lineage_type": None,
                        "raw_json": rel,
                    }
                )

    return extracted


def derive_pedigree_parent_child_relationships(
    ascendancy_map: dict[int, str],
) -> list[dict[str, Any]]:
    """Derives parent-child relationships mathematically from Ahnentafel numbers.

    Rules:
    - Father of ascendancy number A has ascendancy number 2*A.
    - Mother of ascendancy number A has ascendancy number 2*A + 1.
    """
    derived = []
    for asc_num, child_pid in ascendancy_map.items():
        if asc_num <= 0:
            continue

        father_asc = asc_num * 2
        if father_asc in ascendancy_map:
            father_pid = ascendancy_map[father_asc]
            derived.append(
                {
                    "id": f"ahnen_{father_pid}_{child_pid}",
                    "rel_type": "parent-child",
                    "parent_pid": father_pid,
                    "child_pid": child_pid,
                    "spouse1_pid": None,
                    "spouse2_pid": None,
                    "lineage_type": "biological",
                    "raw_json": {
                        "source": "ahnentafel_derivation",
                        "child_asc": asc_num,
                        "parent_asc": father_asc,
                    },
                }
            )

        mother_asc = asc_num * 2 + 1
        if mother_asc in ascendancy_map:
            mother_pid = ascendancy_map[mother_asc]
            derived.append(
                {
                    "id": f"ahnen_{mother_pid}_{child_pid}",
                    "rel_type": "parent-child",
                    "parent_pid": mother_pid,
                    "child_pid": child_pid,
                    "spouse1_pid": None,
                    "spouse2_pid": None,
                    "lineage_type": "biological",
                    "raw_json": {
                        "source": "ahnentafel_derivation",
                        "child_asc": asc_num,
                        "parent_asc": mother_asc,
                    },
                }
            )

    return derived


def calculate_generation_and_path(ascendancy_number: int) -> tuple[int, str]:
    """Calculates generation (0-based) and lineage path from an Ahnentafel number.

    Ahnentafel rules:
    - 1 = root person (gen 0, path='self')
    - 2 = father of 1, 3 = mother of 1 (gen 1)
    - 4 = father of 2 (father's father), 5 = mother of 2, etc.
    """
    if ascendancy_number <= 0:
        return 0, "unknown"

    if ascendancy_number == 1:
        return 0, "self"

    generation = int(math.floor(math.log2(ascendancy_number)))

    # Compute binary path
    # e.g., binary representation without '0b1': 0 -> father, 1 -> mother
    bin_str = bin(ascendancy_number)[3:]  # strip leading '0b1'
    path_tokens = []
    for char in bin_str:
        if char == "0":
            path_tokens.append("father")
        else:
            path_tokens.append("mother")

    return generation, ".".join(path_tokens)


def calculate_global_ahnentafel(frontier_asc: int, sub_asc: int) -> tuple[int, int, str]:
    """Calculates global generation, Ahnentafel number, and lineage path for a sub-pedigree node.

    Args:
        frontier_asc: Global Ahnentafel number of the root of the sub-pedigree (e.g. Gen 7 ancestor).
        sub_asc: Relative Ahnentafel number within that sub-pedigree (1 = the frontier ancestor themselves).

    Returns:
        (global_generation, global_ascendancy_number, global_lineage_path)
    """
    if sub_asc <= 0 or frontier_asc <= 0:
        return 0, 0, "unknown"

    frontier_gen, frontier_path = calculate_generation_and_path(frontier_asc)
    if sub_asc == 1:
        return frontier_gen, frontier_asc, frontier_path

    sub_gen, sub_path = calculate_generation_and_path(sub_asc)
    global_gen = frontier_gen + sub_gen
    global_asc = (frontier_asc << sub_gen) + (sub_asc - (1 << sub_gen))

    # Path concatenation
    if frontier_path == "self":
        global_path = sub_path
    elif sub_path == "self" or not sub_path:
        global_path = frontier_path
    else:
        global_path = f"{frontier_path}.{sub_path}"

    return global_gen, global_asc, global_path

