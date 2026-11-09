from alembic import op
import sqlalchemy as sa


revision = "0004_events"
down_revision = "0003_menu_categories"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("total_amount", sa.Float(), nullable=True))
    op.create_table(
        "kitchen_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False),
    )
    op.create_table(
        "processed_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("consumer", sa.String(50), primary_key=True),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("routing_key", sa.String(100), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_deliveries_order_id", "deliveries", ["order_id"])


def downgrade():
    op.drop_constraint("uq_deliveries_order_id", "deliveries", type_="unique")
    op.drop_table("outbox")
    op.drop_table("processed_events")
    op.drop_table("kitchen_orders")
    op.drop_column("orders", "total_amount")
