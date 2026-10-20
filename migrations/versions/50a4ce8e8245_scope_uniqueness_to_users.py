"""scope uniqueness to users

Revision ID: 50a4ce8e8245
Revises: 8b8ea410224a
Create Date: 2026-10-20 18:56:53.601770

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50a4ce8e8245"
down_revision: str | Sequence[str] | None = "8b8ea410224a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The baseline created unnamed single-column unique constraints. Name them while the
# table is reflected so batch mode can drop them on SQLite.
UNNAMED_UNIQUE_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("recipes", naming_convention=UNNAMED_UNIQUE_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_recipes_name", type_="unique")
        batch_op.create_unique_constraint("uq_recipes_user_pk_name", ["user_pk", "name"])

    with op.batch_alter_table("planned_days", naming_convention=UNNAMED_UNIQUE_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_planned_days_day", type_="unique")
        batch_op.create_unique_constraint("uq_planned_days_user_pk_day", ["user_pk", "day"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("recipes") as batch_op:
        batch_op.drop_constraint("uq_recipes_user_pk_name", type_="unique")
        batch_op.create_unique_constraint("uq_recipes_name", ["name"])

    with op.batch_alter_table("planned_days") as batch_op:
        batch_op.drop_constraint("uq_planned_days_user_pk_day", type_="unique")
        batch_op.create_unique_constraint("uq_planned_days_day", ["day"])
