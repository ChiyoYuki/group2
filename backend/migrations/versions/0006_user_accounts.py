"""User accounts, login sessions and project ownership.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(username)) >= 3", name=op.f("ck_users_username_min_length")
        ),
        sa.CheckConstraint(
            "length(trim(password_hash)) > 0", name=op.f("ck_users_password_hash_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_digest", name=op.f("uq_auth_sessions_token_digest")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("owner_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_projects_owner_id_users"), "users", ["owner_id"], ["id"], ondelete="RESTRICT"
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint(op.f("fk_projects_owner_id_users"), type_="foreignkey")
        batch.drop_column("owner_id")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
