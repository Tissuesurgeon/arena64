"""add media_url and challenge pack enum values

Revision ID: 0002_challenge_packs
Revises: 0001_initial
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_challenge_packs"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum extensions (no-op / ignore if already present)
    for value in ("STADIUM", "PLAYER_ID", "FLAG", "FORMATION"):
        op.execute(
            f"""
            DO $$ BEGIN
                ALTER TYPE challengetype ADD VALUE IF NOT EXISTS '{value}';
            EXCEPTION
                WHEN duplicate_object THEN null;
                WHEN undefined_object THEN null;
            END $$;
            """
        )
    op.add_column("questions", sa.Column("media_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("questions", "media_url")
