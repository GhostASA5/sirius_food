from alembic import op
import sqlalchemy as sa

revision = "0008_observability"
down_revision = "0007_loyalty"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("outbox", sa.Column("context", sa.String(), nullable=True))


def downgrade():
    op.drop_column("outbox", "context")
