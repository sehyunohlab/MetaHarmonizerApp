"""fix ontology codes that named other concepts

The dictionary fallback's code table (app/services/harmonizer.py) gave 60
entries the code of another concept: United States and United Kingdom swapped,
Japan coded as Kenya, Bone Marrow Aspirate as Human Chromosome Y, and so on.
Rows mapped, edited or remembered with those codes keep them, so this rewrites
each (term, wrong code) pair to the term's real code: NCI EVS (NCIt 26.09d),
OLS4 (HANCESTRO 2025-10-14), and the lab's cBioPortal data dictionary for age
groups and ancestry. Only those exact pairs change; a term with its right code
(United Kingdom, NCIT:C17233) is left alone. Three rendered terms that are not
NCIt names are renamed to the NCIt name of their code.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None

# (term as written, wrong code, right code or None, renamed term or None)
FIXES: list[tuple[str, str, str | None, str | None]] = [
    # cancer_status
    ("Tumor Status - Free", "NCIT:C17629", "NCIT:C156848", "Tumor Free"),
    ("Tumor Free", "NCIT:C17629", "NCIT:C156848", None),
    ("Tumor Status - With Tumor", "NCIT:C13104", "NCIT:C156849", "With Tumor"),
    ("With Tumor", "NCIT:C13104", "NCIT:C156849", None),
    ("No Evidence of Disease", "NCIT:C5641", "NCIT:C40413", None),
    # specimen_type
    ("Biopsy Specimen", "NCIT:C18009", "NCIT:C18202", None),
    ("Bone Marrow Aspirate", "NCIT:C13286", "NCIT:C133261", None),
    ("Cell Line", "NCIT:C12508", "NCIT:C16403", None),
    ("Peripheral Blood", "NCIT:C25269", "NCIT:C173496", None),
    ("Resection Specimen", "NCIT:C15189", "NCIT:C158758", "Resection"),
    ("Resection", "NCIT:C15189", "NCIT:C158758", None),
    ("Xenograft", "NCIT:C19302", "NCIT:C12932", None),
    ("Organoid", "NCIT:C172923", "NCIT:C172259", None),
    ("Leukocyte Sample", "NCIT:C12529", "NCIT:C189087", None),
    # age_group
    ("Newborn", "NCIT:C14174", "NCIT:C16731", None),
    ("Elderly", "NCIT:C9369", "NCIT:C16268", None),
    ("School Age Child", "NCIT:C89831", "NCIT:C85405", None),
    ("Children 2-11 Years Old", "NCIT:C89831", "NCIT:C49683", None),
    ("Senior", "NCIT:C25195", None, None),  # NCIt has no age group named Senior
    # ancestry
    ("African Ancestry", "NCIT:C43234", "HANCESTRO:0010", None),
    ("Asian Ancestry", "NCIT:C43469", "HANCESTRO:0008", None),
    ("European Ancestry", "NCIT:C43851", "HANCESTRO:0005", None),
    ("Latin or Admixed American", "NCIT:C43462", "HANCESTRO:0014", None),
    ("Indigenous American", "NCIT:C43462", "HANCESTRO:0013", None),
    # country
    ("Brazil", "NCIT:C16374", "NCIT:C16364", None),
    ("Canada", "NCIT:C16482", "NCIT:C16380", None),
    ("China", "NCIT:C16448", "NCIT:C16428", None),
    ("Denmark", "NCIT:C16500", "NCIT:C16496", None),
    ("Finland", "NCIT:C16586", "NCIT:C16584", None),
    ("India", "NCIT:C16726", "NCIT:C16727", None),
    ("Japan", "NCIT:C16769", "NCIT:C16764", None),
    ("South Korea", "NCIT:C17202", "NCIT:C16774", None),
    ("Korea, Republic of", "NCIT:C17202", "NCIT:C16774", None),
    ("Poland", "NCIT:C16954", "NCIT:C17002", None),
    ("Singapore", "NCIT:C17132", "NCIT:C17134", None),
    ("United Kingdom", "NCIT:C17234", "NCIT:C17233", None),
    ("United States", "NCIT:C17233", "NCIT:C17234", None),
    ("Viet Nam", "NCIT:C17239", "NCIT:C17252", None),
    # disease
    ("Adenoma", "NCIT:C3220", "NCIT:C2855", None),
    ("Colorectal Cancer", "NCIT:C9382", "NCIT:C2955", None),
    ("Healthy Subject", "NCIT:C35429", "NCIT:C49651", None),
    ("Ulcerative Colitis", "NCIT:C3343", "NCIT:C2952", None),
    # study_design
    ("Cross-Sectional Study", "NCIT:C15208", "NCIT:C53310", None),
]

# (table, term column, code column)
COLUMNS = [
    ("ontology_mappings", "ontology_term", "ontology_id"),
    ("ontology_mappings", "curator_term", "curator_id"),
    ("learned_decisions", "target_term", "target_id"),
    ("learned_decision_dismissals", "target_term", "target_id"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for table, term_col, code_col in COLUMNS:
        for term, wrong, right, renamed in FIXES:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET {code_col} = :right, {term_col} = COALESCE(:renamed, {term_col}) "
                    f"WHERE lower({term_col}) = lower(:term) AND {code_col} = :wrong"
                ),
                {"term": term, "wrong": wrong, "right": right, "renamed": renamed},
            )


def downgrade() -> None:
    # The old codes named other concepts; restoring them would only restore the bug.
    pass
