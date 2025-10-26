"""Enforce uniqueness on committee acronyms and slugs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "10_committee_acronym_uniqueness"
down_revision: Union[str, None] = "9_committee_metadata_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _constraint_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(table)
    return any(constraint["name"] == name for constraint in constraints)


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table)
    return any(index["name"] == name for index in indexes)


def upgrade() -> None:
    """Clean committee acronyms and add uniqueness guarantees."""
    # Normalize acronym casing to avoid duplicate variants
    op.execute(
        """
        UPDATE committees
        SET acronym_en = UPPER(TRIM(acronym_en))
        WHERE acronym_en IS NOT NULL
        """
    )

    # Remove duplicate acronyms per jurisdiction, keeping the lowest id row
    op.execute(
        """
        DELETE FROM committees c
        USING committees dup
        WHERE c.id > dup.id
          AND c.jurisdiction = dup.jurisdiction
          AND c.acronym_en IS NOT NULL
          AND dup.acronym_en IS NOT NULL
          AND UPPER(c.acronym_en) = UPPER(dup.acronym_en)
        """
    )

    # Ensure slug uniqueness constraint exists
    if not _constraint_exists("committees", "uq_committee_slug"):
        with op.batch_alter_table("committees") as batch_op:
            batch_op.create_unique_constraint(
                "uq_committee_slug", ["committee_slug"])

    # Create acronym unique constraint and supporting index
    if not _constraint_exists("committees", "uq_committee_acronym"):
        with op.batch_alter_table("committees") as batch_op:
            batch_op.create_unique_constraint(
                "uq_committee_acronym",
                ["jurisdiction", "acronym_en"],
            )

    if not _index_exists("committees", "idx_committee_acronym"):
        op.create_index(
            "idx_committee_acronym",
            "committees",
            ["jurisdiction", "acronym_en"],
        )


def downgrade() -> None:
    """Remove acronym uniqueness guarantees."""
    if _index_exists("committees", "idx_committee_acronym"):
        op.drop_index("idx_committee_acronym", table_name="committees")

    if _constraint_exists("committees", "uq_committee_acronym"):
        with op.batch_alter_table("committees") as batch_op:
            batch_op.drop_constraint("uq_committee_acronym", type_="unique")
