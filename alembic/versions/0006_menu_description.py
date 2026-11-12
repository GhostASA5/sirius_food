from alembic import op
import sqlalchemy as sa


revision = "0006_menu_description"
down_revision = "0005_processed_event_id"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("menu_items", sa.Column("description", sa.String(), nullable=True))


def downgrade():
    op.drop_column("menu_items", "description")
