from alembic import op
import sqlalchemy as sa


revision = "0003_menu_categories"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "menu_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )
    op.create_index("ix_menu_categories_id", "menu_categories", ["id"])
    with op.batch_alter_table("menu_items") as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_menu_items_category", "menu_categories", ["category_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("menu_items") as batch_op:
        batch_op.drop_constraint("fk_menu_items_category", type_="foreignkey")
        batch_op.drop_column("category_id")
    op.drop_table("menu_categories")
