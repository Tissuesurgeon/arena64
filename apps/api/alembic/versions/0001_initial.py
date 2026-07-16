"""Initial schema placeholder — runtime create_all covers MVP; generate revision when DB is up.

Revision ID: 0001
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables created via SQLAlchemy metadata.create_all on startup for MVP.
    pass


def downgrade() -> None:
    pass