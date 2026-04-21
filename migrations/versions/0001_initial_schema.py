"""initial schema: jobs and records tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── jobstatus enum ────────────────────────────────────────────────────────
    # Use a PL/pgSQL DO block for idempotent type creation.
    # postgresql.ENUM(...).create(checkfirst=True) does not work reliably with
    # asyncpg because the checkfirst SELECT runs on a sync cursor inside an
    # async connection, silently skipping the check and issuing CREATE TYPE
    # unconditionally — which fails with DuplicateObjectError on re-runs.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE jobstatus AS ENUM ('pending', 'running', 'success', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "status",
            # Use postgresql.ENUM (not sa.Enum) with create_type=False.
            # sa.Enum fires a before_create event in SQLAlchemy 2.0.x that ignores
            # create_type=False and tries to CREATE TYPE a second time.
            # postgresql.ENUM respects the flag and skips type creation entirely.
            postgresql.ENUM(
                "pending", "running", "success", "failed",
                name="jobstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("fecha_inicial", sa.Date(), nullable=False),
        sa.Column("fecha_final", sa.Date(), nullable=False),
        sa.Column("limit_requested", sa.Integer(), nullable=False),
        sa.Column("total_extracted", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── records ───────────────────────────────────────────────────────────────
    op.create_table(
        "records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_row_id", sa.String(128), nullable=True),
        sa.Column("patient_name", sa.String(512), nullable=True),
        sa.Column("patient_document", sa.String(64), nullable=True),
        sa.Column("date_service_or_facturation", sa.Date(), nullable=True),
        sa.Column("site", sa.String(256), nullable=True),
        sa.Column("contract", sa.String(256), nullable=True),
        sa.Column("raw_row_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── indexes ───────────────────────────────────────────────────────────────
    op.create_index("ix_records_job_id", "records", ["job_id"])
    op.create_index("ix_records_external_row_id", "records", ["external_row_id"])
    op.create_index("ix_records_patient_document", "records", ["patient_document"])


def downgrade() -> None:
    op.drop_index("ix_records_patient_document", table_name="records")
    op.drop_index("ix_records_external_row_id", table_name="records")
    op.drop_index("ix_records_job_id", table_name="records")
    op.drop_table("records")
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS jobstatus")
