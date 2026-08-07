"""align subscription user uniqueness index

Revision ID: g7e1c3d6f864
Revises: f6d0b2c5e753
Create Date: 2026-08-07 00:45:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "g7e1c3d6f864"
down_revision: Union[str, None] = "f6d0b2c5e753"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("subscriptions_user_id_key", "subscriptions", type_="unique")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False)
    op.create_unique_constraint("subscriptions_user_id_key", "subscriptions", ["user_id"])
