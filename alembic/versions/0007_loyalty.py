from alembic import op
import sqlalchemy as sa


revision = "0007_loyalty"
down_revision = "0006_menu_description"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders") as batch:
        batch.alter_column("total_amount", existing_type=sa.Float(), type_=sa.Numeric(16, 2))
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("discount_type", sa.String(10), nullable=False),
        sa.Column("discount_value", sa.Numeric(16, 2), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer, nullable=False),
        sa.Column("current_uses", sa.Integer, nullable=False),
        sa.Column("min_order_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("once_per_user", sa.Boolean, nullable=False),
    )
    op.create_index("ix_promo_codes_valid_until", "promo_codes", ["valid_until"])
    op.create_table(
        "promo_code_usages",
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), primary_key=True),
        sa.Column("promo_id", sa.Integer, sa.ForeignKey("promo_codes.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_table(
        "loyalty_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("balance", sa.Numeric(16, 2), nullable=False),
        sa.Column("total_earned", sa.Numeric(16, 2), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
    )
    op.create_table(
        "loyalty_transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("loyalty_accounts.id"), nullable=False),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
    )
    op.create_index("ix_loyalty_transactions_account_id", "loyalty_transactions", ["account_id"])


def downgrade():
    for table in ("loyalty_transactions", "loyalty_accounts", "promo_code_usages", "promo_codes"):
        op.drop_table(table)
    with op.batch_alter_table("orders") as batch:
        batch.alter_column("total_amount", existing_type=sa.Numeric(16, 2), type_=sa.Float())
