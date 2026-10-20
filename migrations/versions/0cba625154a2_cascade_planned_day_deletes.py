"""cascade planned day deletes

Revision ID: 0cba625154a2
Revises: 50a4ce8e8245
Create Date: 2026-10-20 18:58:39.569613

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0cba625154a2"
down_revision: str | Sequence[str] | None = "50a4ce8e8245"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The baseline created unnamed foreign keys. Name them while the table is
# reflected so batch mode can replace the recipe key on SQLite.
FOREIGN_KEY_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("planned_days", naming_convention=FOREIGN_KEY_CONVENTION) as batch_op:
        batch_op.drop_constraint("fk_planned_days_recipe_pk_recipes", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_planned_days_recipe_pk_recipes", "recipes", ["recipe_pk"], ["pk"], ondelete="CASCADE"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("planned_days", naming_convention=FOREIGN_KEY_CONVENTION) as batch_op:
        batch_op.drop_constraint("fk_planned_days_recipe_pk_recipes", type_="foreignkey")
        batch_op.create_foreign_key("fk_planned_days_recipe_pk_recipes", "recipes", ["recipe_pk"], ["pk"])
