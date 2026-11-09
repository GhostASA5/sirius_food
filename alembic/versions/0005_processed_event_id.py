from alembic import op
import sqlalchemy as sa


revision = "0005_processed_event_id"
down_revision = "0004_events"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "processed_events", "id", existing_type=sa.Integer(),
            type_=sa.String(36), postgresql_using="id::varchar",
        )
    else:
        with op.batch_alter_table("processed_events") as batch:
            batch.alter_column("id", existing_type=sa.Integer(), type_=sa.String(36))


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "processed_events", "id", existing_type=sa.String(36),
            type_=sa.Integer(), postgresql_using="id::integer",
        )
    else:
        with op.batch_alter_table("processed_events") as batch:
            batch.alter_column("id", existing_type=sa.String(36), type_=sa.Integer())
