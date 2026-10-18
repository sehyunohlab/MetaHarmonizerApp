"""Dashboard-owned value-to-ontology helpers (the engine pipeline lives behind
``app.engine_adapter``).

Exposes:
- ``ONTOLOGY_MAP``          curated raw→canonical mappings + fallback source.
- ``_STATIC_NCIT``          canonical term → NCIt/UBERON/HANCESTRO code table.
- ``_load_field_value_dict``  field → canonical values (field_value_dict.json).
- ``run_ontology_mapping``  the dashboard's value-mapping routine.
- ``generate_study_id``     filename → unique study id.
"""

from __future__ import annotations

import json as _json
import logging
import re
import uuid
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


# Paths

# backend/data/ — dashboard-owned read-only assets (curated value dictionaries,
# the NCI EVS cache, etc.). Survives removal of the legacy vendored engine.
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_SCHEMA_DIR = _DATA_DIR / "schema"
_NCI_CACHE_PATH = _DATA_DIR / "nci_cache.json"


# Static term → ontology code table: the first lookup for a canonical value's
# code, before the NCI EVS cache. Each code is the concept of that name (or
# synonym) in its ontology; scripts/verify_ontology_codes.py checks every entry
# against NCI EVS and OLS4 and records what it found in
# data/schema/ontology_code_labels.json (pinned by tests). Age groups and
# ancestry follow the lab's cBioPortal data dictionary (OmicsMLRepoData,
# inst/extdata/cBioPortal_data_dictionary.csv): its age-group codes, and the
# children of HANCESTRO:0004 for ancestry. Unprefixed codes are NCIt.

_STATIC_NCIT: dict[str, str] = {
    # sex
    "male": "C20197", "female": "C16576",
    # vital_status
    "alive": "C37987", "dead": "C28554",
    # cancer_status
    "tumor free": "C156848", "with tumor": "C156849",
    "no evidence of disease": "C40413",
    # specimen_type
    "biopsy specimen": "C18202", "bone marrow aspirate": "C133261",
    "cell line": "C16403", "peripheral blood": "C173496",
    "resection": "C158758", "xenograft": "C12932",
    "organoid": "C172259", "leukocyte sample": "C189087",
    "patient derived xenograft": "C122936",
    "circulating cell-free dna": "C128274",
    # sample_type
    "primary neoplasm": "C8509", "metastatic neoplasm": "C3261",
    "recurrent neoplasm": "C4798", "neoplasm": "C3262",
    "benign neoplasm": "C3677", "clinical relapse": "C191345",
    "distant metastasis": "C18206", "locally recurrent disease": "C176551",
    # age_group
    "newborn": "C16731", "infant": "C27956", "child": "C16423",
    "adolescent": "C27954", "adult": "C17600", "elderly": "C16268",
    # ancestry
    "african ancestry": "HANCESTRO:0010",
    "african american or afro-caribbean ancestry": "HANCESTRO:0016",
    "asian ancestry": "HANCESTRO:0008",
    "european ancestry": "HANCESTRO:0005",
    "greater middle eastern (middle eastern or north african or persian)": "HANCESTRO:0015",
    "indigenous american": "HANCESTRO:0013",
    "latin or admixed american": "HANCESTRO:0014",
    "oceanian": "HANCESTRO:0017",
    # country (names, and ISO 3166 alpha-3 codes)
    "australia": "C16311", "aus": "C16311",
    "brazil": "C16364", "bra": "C16364",
    "bulgaria": "C16368",
    "canada": "C16380", "can": "C16380",
    "china": "C16428", "chn": "C16428",
    "croatia": "C16474",
    "denmark": "C16496", "dnk": "C16496",
    "finland": "C16584", "fin": "C16584",
    "france": "C16592", "fra": "C16592",
    "germany": "C16636", "deu": "C16636",
    "india": "C16727", "ind": "C16727",
    "iraq": "C16756",
    "italy": "C16761", "ita": "C16761",
    "japan": "C16764", "jpn": "C16764",
    "korea, republic of": "C16774", "south korea": "C16774", "kor": "C16774",
    "mexico": "C16850",
    "moldova, republic of": "C16871",
    "netherlands": "C16903", "nld": "C16903",
    "philippines": "C16978",
    "poland": "C17002", "pol": "C17002",
    "romania": "C17108",
    "russian federation": "C17111",
    "serbia": "C64377",
    "singapore": "C17134", "sgp": "C17134",
    "spain": "C17152", "esp": "C17152",
    "sweden": "C17180", "swe": "C17180",
    "ukraine": "C17229",
    "united kingdom": "C17233", "gbr": "C17233",
    "united states": "C17234", "usa": "C17234",
    "viet nam": "C17252", "vnm": "C17252",
    # body_site
    "feces": "UBERON:0001988", "stool": "UBERON:0001988",
    "blood": "UBERON:0000178", "colon": "UBERON:0001155",
    # disease
    "adenoma": "C2855",
    "colorectal carcinoma": "C2955", "colorectal cancer": "C2955", "crc": "C2955",
    "inflammatory bowel disease": "C3138", "ibd": "C3138",
    "crohn disease": "C2965", "cd": "C2965",
    "ulcerative colitis": "C2952", "uc": "C2952",
    "type 1 diabetes": "C2986", "t1d": "C2986",
    "type 2 diabetes": "C26747", "t2d": "C26747",
    # study_design
    "case-control": "C15197",
    # treatment_type (a subset – there are 100 values; key ones below)
    "surgery": "C17173", "chemotherapy": "C15632", "radiation": "C15313",
    "immunotherapy": "C15262",
}

# ---------------------------------------------------------------------------
# Ontology value mappings kept for legacy fallback + ontology router index.
# The live run_ontology_mapping() also uses field_value_dict.json (broader).
# ---------------------------------------------------------------------------

ONTOLOGY_MAP: dict[str, dict[str, tuple[str, str]]] = {
    "body_site": {
        "stool": ("feces", "UBERON:0001988"),
        "feces": ("feces", "UBERON:0001988"),
        "blood": ("Blood", "UBERON:0000178"),
        "colon": ("Colon", "UBERON:0001155"),
        "liver": ("Liver", "UBERON:0002107"),
        "lung": ("Lung", "UBERON:0002048"),
        "skin": ("Skin", "UBERON:0002097"),
    },
    "sex": {
        "male": ("Male", "NCIT:C20197"),
        "female": ("Female", "NCIT:C16576"),
        "m": ("Male", "NCIT:C20197"),
        "f": ("Female", "NCIT:C16576"),
        "1": ("Male", "NCIT:C20197"),
        "2": ("Female", "NCIT:C16576"),
    },
    "country": {
        "can": ("Canada", "NCIT:C16380"),
        "canada": ("Canada", "NCIT:C16380"),
        "usa": ("United States", "NCIT:C17234"),
        "us": ("United States", "NCIT:C17234"),
        "united states": ("United States", "NCIT:C17234"),
        "italy": ("Italy", "NCIT:C16761"),
        "ita": ("Italy", "NCIT:C16761"),
        "chn": ("China", "NCIT:C16428"),
        "china": ("China", "NCIT:C16428"),
        "gbr": ("United Kingdom", "NCIT:C17233"),
        "uk": ("United Kingdom", "NCIT:C17233"),
        "deu": ("Germany", "NCIT:C16636"),
        "germany": ("Germany", "NCIT:C16636"),
        "fra": ("France", "NCIT:C16592"),
        "france": ("France", "NCIT:C16592"),
        "aus": ("Australia", "NCIT:C16311"),
        "australia": ("Australia", "NCIT:C16311"),
        "swe": ("Sweden", "NCIT:C17180"),
        "sweden": ("Sweden", "NCIT:C17180"),
        "nld": ("Netherlands", "NCIT:C16903"),
        "esp": ("Spain", "NCIT:C17152"),
        "spain": ("Spain", "NCIT:C17152"),
        "jpn": ("Japan", "NCIT:C16764"),
        "japan": ("Japan", "NCIT:C16764"),
        "kor": ("South Korea", "NCIT:C16774"),
        "ind": ("India", "NCIT:C16727"),
        "india": ("India", "NCIT:C16727"),
        "bra": ("Brazil", "NCIT:C16364"),
        "brazil": ("Brazil", "NCIT:C16364"),
        "dnk": ("Denmark", "NCIT:C16496"),
        "fin": ("Finland", "NCIT:C16584"),
        "sgp": ("Singapore", "NCIT:C17134"),
        "vnm": ("Viet Nam", "NCIT:C17252"),
        "pol": ("Poland", "NCIT:C17002"),
    },
    "disease": {
        "adenoma": ("Adenoma", "NCIT:C2855"),
        "healthy": ("Healthy Subject", "NCIT:C49651"),
        "normal": ("Normal", "NCIT:C14165"),
        # The lab's disease map: COLORECTAL CANCER -> Colorectal Carcinoma.
        "crc": ("Colorectal Carcinoma", "NCIT:C2955"),
        "colorectal cancer": ("Colorectal Carcinoma", "NCIT:C2955"),
        "ibd": ("Inflammatory Bowel Disease", "NCIT:C3138"),
        "cd": ("Crohn Disease", "NCIT:C2965"),
        "crohn disease": ("Crohn Disease", "NCIT:C2965"),
        "uc": ("Ulcerative Colitis", "NCIT:C2952"),
        "ulcerative colitis": ("Ulcerative Colitis", "NCIT:C2952"),
        "t1d": ("Type 1 Diabetes Mellitus", "NCIT:C2986"),
        "t2d": ("Type 2 Diabetes Mellitus", "NCIT:C26747"),
    },
    # The lab dictionary's age groups; its Child is 2 to under 11 years.
    "age_group": {
        "newborn": ("Newborn", "NCIT:C16731"),
        "infant": ("Infant", "NCIT:C27956"),
        "child": ("Child", "NCIT:C16423"),
        "children 2-11 years old": ("Child", "NCIT:C16423"),
        "adolescent": ("Adolescent", "NCIT:C27954"),
        "adult": ("Adult", "NCIT:C17600"),
        "elderly": ("Elderly", "NCIT:C16268"),
    },
    "vital_status": {
        "alive": ("Alive", "NCIT:C37987"),
        "dead": ("Dead", "NCIT:C28554"),
        "deceased": ("Dead", "NCIT:C28554"),
        "living": ("Alive", "NCIT:C37987"),
        "dead with tumor": ("Dead", "NCIT:C28554"),
    },
    "cancer_status": {
        "tumor free": ("Tumor Free", "NCIT:C156848"),
        "with tumor": ("With Tumor", "NCIT:C156849"),
        "ned": ("No Evidence of Disease", "NCIT:C40413"),
        "no evidence of disease": ("No Evidence of Disease", "NCIT:C40413"),
    },
    "specimen_type": {
        "biopsy": ("Biopsy Specimen", "NCIT:C18202"),
        "biopsy specimen": ("Biopsy Specimen", "NCIT:C18202"),
        "blood": ("Peripheral Blood", "NCIT:C173496"),
        "peripheral blood": ("Peripheral Blood", "NCIT:C173496"),
        "resection": ("Resection", "NCIT:C158758"),
        "cell line": ("Cell Line", "NCIT:C16403"),
        "xenograft": ("Xenograft", "NCIT:C12932"),
        "organoid": ("Organoid", "NCIT:C172259"),
    },
    # Children of HANCESTRO:0004, whose synonyms include european, caucasian and white.
    "ancestry": {
        "african": ("African Ancestry", "HANCESTRO:0010"),
        "african ancestry": ("African Ancestry", "HANCESTRO:0010"),
        "african american": ("African American or Afro-Caribbean Ancestry", "HANCESTRO:0016"),
        "asian": ("Asian Ancestry", "HANCESTRO:0008"),
        "asian ancestry": ("Asian Ancestry", "HANCESTRO:0008"),
        "european": ("European Ancestry", "HANCESTRO:0005"),
        "european ancestry": ("European Ancestry", "HANCESTRO:0005"),
        "caucasian": ("European Ancestry", "HANCESTRO:0005"),
        "white": ("European Ancestry", "HANCESTRO:0005"),
        "hispanic": ("Latin or Admixed American", "HANCESTRO:0014"),
        "latino": ("Latin or Admixed American", "HANCESTRO:0014"),
    },
    "sample_type": {
        "primary": ("Primary Neoplasm", "NCIT:C8509"),
        "primary neoplasm": ("Primary Neoplasm", "NCIT:C8509"),
        "metastatic": ("Metastatic Neoplasm", "NCIT:C3261"),
        "metastatic neoplasm": ("Metastatic Neoplasm", "NCIT:C3261"),
        "recurrent": ("Recurrent Neoplasm", "NCIT:C4798"),
        "recurrent neoplasm": ("Recurrent Neoplasm", "NCIT:C4798"),
        "benign": ("Benign Neoplasm", "NCIT:C3677"),
    },
    "study_design": {
        "case-control": ("Case-Control Study", "NCIT:C15197"),
        "observational": ("Observational Study", "NCIT:C16084"),
        "longitudinal": ("Longitudinal Study", "NCIT:C15273"),
        "cross-sectional": ("Cross-Sectional Study", "NCIT:C53310"),
        "cross-sectional observational": ("Cross-Sectional Study", "NCIT:C53310"),
    },
}


# Confidence thresholds (used by run_ontology_mapping)
THRESHOLD_AUTO_ACCEPT = 0.90


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(name: str) -> str:
    """Lowercase, strip, replace separators with underscore."""
    s = name.strip().lower()
    s = re.sub(r"[\s\-\.]+", "_", s)
    return s


# Cached field_value_dict.json (loaded once on first ontology mapping call)
_cached_field_value_dict: dict | None = None


def _load_field_value_dict() -> dict[str, list[str]]:
    """
    Load field_value_dict.json from backend/data/schema/.

    Returns {field_name: [canonical_value, ...]} for the curated fields.
    Cached at module level after first call.
    """
    global _cached_field_value_dict
    if _cached_field_value_dict is not None:
        return _cached_field_value_dict

    path = _SCHEMA_DIR / "field_value_dict.json"
    if path.exists():
        try:
            with open(path) as f:
                _cached_field_value_dict = _json.load(f)
            logger.info(
                "Loaded field_value_dict: %d fields",
                len(_cached_field_value_dict),
            )
        except Exception as e:
            logger.warning("Could not load field_value_dict.json: %s", e)
            _cached_field_value_dict = {}
    else:
        logger.warning("field_value_dict.json not found at %s", path)
        _cached_field_value_dict = {}
    return _cached_field_value_dict


def supports_ontology_mapping(field: str | None, target_schema: str | None = None) -> bool:
    """True when a field's values are mapped to ontology terms: by the value
    dictionary, or by the ontology engine (an engine corpus for the field, or
    one its target schema's data dictionary declares)."""
    if not field:
        return False
    key = _normalise(field)
    if key in ONTOLOGY_MAP or key in {_normalise(name) for name in _load_field_value_dict()}:
        return True
    from app.engine_adapter import is_ontology_field

    return is_ontology_field(field, target_schema)


def _resolve_ncit_id(term: str, nci_term2code: dict, field: str) -> str | None:
    """
    Resolve a canonical term name to a NCIT/UBERON ID.
    Lookup order:
      1. Static _STATIC_NCIT table (term lowercase key)
      2. Persisted NCI API cache (nci_term2code, term lowercase key)
      3. ONTOLOGY_MAP for the same field.
    """
    key = term.strip().lower()

    # 1. Static table
    code = _STATIC_NCIT.get(key)
    if code:
        prefix = "UBERON" if code.startswith("UBERON") else "NCIT"
        return code if ":" in code else f"{prefix}:{code}"

    # 2. NCI API cache (populated by previous live API runs)
    code = nci_term2code.get(key)
    if code:
        return f"NCIT:{code}"

    # 3. Check ONTOLOGY_MAP legacy entries for this term
    for _field, vmap in ONTOLOGY_MAP.items():
        if _field != field:
            continue
        for _raw, (mapped_term, mapped_id) in vmap.items():
            if mapped_term.lower() == key and mapped_id:
                return mapped_id

    return None


def run_ontology_mapping(
    raw_df: pd.DataFrame,
    schema_mappings: list[dict],
) -> list[dict]:
    """
    Map raw column values to canonical ontology terms and IDs.

    Primary source: backend/data/schema/field_value_dict.json (curated values
    for fields like treatment_type, vital_status, ancestry, cancer_status,
    specimen_type, sample_type, country, sex, …).

    Supplemental source: ONTOLOGY_MAP (covers body_site, disease, age_group,
    sample_type additions, ancestry, vital_status, cancer_status, specimen_type,
    study_design — extends the value-dict coverage).

    Matching:
      - Exact lowercase match → score 1.0
      - RapidFuzz token_sort_ratio ≥ 70 → score proportional to ratio
      - Below 70 → term=None, id=None, score=0.0 (recorded for audit)

    NCIT IDs are resolved via _STATIC_NCIT → NCI API cache → ONTOLOGY_MAP fallback.
    """
    onto_results: list[dict] = []

    field_value_dict = _load_field_value_dict()

    nci_term2code: dict[str, str] = {}
    try:
        if _NCI_CACHE_PATH.exists():
            with open(_NCI_CACHE_PATH) as f:
                cache_data = _json.load(f)
            nci_term2code = {
                k.lower(): v for k, v in cache_data.get("term2code", {}).items()
            }
    except Exception as e:
        logger.debug("Could not read NCI cache for ontology lookup: %s", e)

    # Merge: primary value_dict + ONTOLOGY_MAP (keyed by lowercase canonical value).
    # Structure: combined_map[field][raw_lower] = (canonical_term, resolved_id_or_None)
    def _build_combined_map() -> dict[str, dict[str, tuple[str, str | None]]]:
        combined: dict[str, dict[str, tuple[str, str | None]]] = {}

        for field, values in field_value_dict.items():
            combined.setdefault(field, {})
            for v in values:
                v_lower = v.strip().lower()
                resolved_id = _resolve_ncit_id(v, nci_term2code, field)
                combined[field][v_lower] = (v, resolved_id)

        for field, vmap in ONTOLOGY_MAP.items():
            combined.setdefault(field, {})
            for raw_lower, (term, ont_id) in vmap.items():
                existing = combined[field].get(raw_lower)
                if existing is None or (existing[1] is None and ont_id):
                    combined[field][raw_lower] = (term, ont_id if ont_id else None)

        return combined

    combined_map = _build_combined_map()

    for mapping in schema_mappings:
        matched = mapping.get("matched_field")
        if not matched or matched not in combined_map:
            continue

        raw_col = mapping["raw_column"]
        if raw_col not in raw_df.columns:
            continue

        value_map = combined_map[matched]
        known_lower_list = list(value_map.keys())
        unique_vals = raw_df[raw_col].dropna().unique()

        for val in unique_vals:
            val_lower = str(val).strip().lower()

            if val_lower in value_map:
                term, ont_id = value_map[val_lower]
                score = 1.0
            else:
                fuzzy_result = process.extractOne(
                    val_lower, known_lower_list, scorer=fuzz.token_sort_ratio
                )
                if fuzzy_result and fuzzy_result[1] >= 70:
                    matched_key = fuzzy_result[0]
                    term, ont_id = value_map[matched_key]
                    score = round(fuzzy_result[1] / 100, 3)
                else:
                    term = None
                    ont_id = None
                    score = 0.0

            onto_results.append({
                "field_name": matched,
                "raw_value": str(val),
                "ontology_term": term,
                "ontology_id": ont_id,
                "confidence_score": score,
                "status": "accepted" if score >= THRESHOLD_AUTO_ACCEPT else "pending",
            })

    return onto_results


def generate_study_id(filename: str) -> str:
    """Create a study ID from the filename."""
    stem = Path(filename).stem
    short_uuid = uuid.uuid4().hex[:8]
    return f"{stem}_{short_uuid}"
