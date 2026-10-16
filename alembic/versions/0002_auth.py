from alembic import op
import sqlalchemy as sa


revision = "0002_auth"
down_revision = "0001_mvp"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("role_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_users_role", "roles", ["role_id"], ["id"])
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("INSERT INTO roles (name) VALUES ('student'), ('cook'), ('courier'), ('admin')")
    op.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'student')")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("role_id", nullable=False)


def downgrade():
    op.drop_table("refresh_tokens")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_role", type_="foreignkey")
        batch_op.drop_column("role_id")
        batch_op.drop_column("password_hash")
    op.drop_table("roles")
