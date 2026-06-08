"""add case insensitive email username unique indexes

Revision ID: 9f6394ee1641
Revises: cb90f8a877a4
Create Date: 2026-06-08 14:30:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '9f6394ee1641'
down_revision: str | Sequence[str] | None = 'cb90f8a877a4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _assert_no_case_insensitive_duplicates(conn) -> None:
    email_dupes = conn.execute(sa.text("""
        SELECT lower(email) AS normalized_email, count(*) AS cnt
        FROM users
        WHERE deleted_at IS NULL AND email IS NOT NULL
        GROUP BY lower(email)
        HAVING count(*) > 1
        LIMIT 5
    """)).fetchall()
    if email_dupes:
        samples = ", ".join(f"{row.normalized_email}({row.cnt})" for row in email_dupes)
        raise RuntimeError(
            f"迁移中止：发现仅大小写不同的重复邮箱，请先人工合并后再迁移。示例: {samples}"
        )

    username_dupes = conn.execute(sa.text("""
        SELECT lower(username) AS normalized_username, count(*) AS cnt
        FROM users
        WHERE deleted_at IS NULL AND username IS NOT NULL
        GROUP BY lower(username)
        HAVING count(*) > 1
        LIMIT 5
    """)).fetchall()
    if username_dupes:
        samples = ", ".join(f"{row.normalized_username}({row.cnt})" for row in username_dupes)
        raise RuntimeError(
            f"迁移中止：发现仅大小写不同的重复用户名，请先人工合并后再迁移。示例: {samples}"
        )


def upgrade() -> None:
    conn = op.get_bind()
    _assert_no_case_insensitive_duplicates(conn)

    op.execute(sa.text("UPDATE users SET email = lower(email) WHERE email IS NOT NULL"))
    op.execute(sa.text("UPDATE users SET username = lower(username) WHERE username IS NOT NULL"))

    op.drop_index('uq_users_username', table_name='users', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_constraint('users_email_key', 'users', type_='unique')

    op.create_index(
        'uq_users_email_lower',
        'users',
        [sa.text('lower(email)')],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL AND email IS NOT NULL'),
    )
    op.create_index(
        'uq_users_username_lower',
        'users',
        [sa.text('lower(username)')],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL AND username IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_users_username_lower',
        table_name='users',
        postgresql_where=sa.text('deleted_at IS NULL AND username IS NOT NULL'),
    )
    op.drop_index(
        'uq_users_email_lower',
        table_name='users',
        postgresql_where=sa.text('deleted_at IS NULL AND email IS NOT NULL'),
    )

    op.create_unique_constraint('users_email_key', 'users', ['email'])
    op.create_index(
        'uq_users_username',
        'users',
        ['username'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
