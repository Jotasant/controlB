"""Grupo próprio por instância, sem herdar permissões de equipes comerciais."""

import sqlalchemy as sa

from alembic import op

revision = "f93b80c256d4"
down_revision = "e82a7fb145c3"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "chat_team",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "chat_team_member",
        sa.Column(
            "team_id",
            sa.UUID(),
            sa.ForeignKey("chat_team.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    # O grupo segue a conexão lógica; usuários serão escolhidos explicitamente.
    # Não copiar membros de vendas, nem conceder acesso implícito a administradores.
    op.execute(
        "INSERT INTO chat_team (id, organization_id, name) SELECT id, organization_id, name FROM chat_connection"
    )
    for table in ("chat_connection", "chat_conversation", "chat_message"):
        op.drop_constraint(f"fk_{table}_team", table, type_="foreignkey")
    op.execute("UPDATE chat_connection SET team_id=id")
    op.execute("UPDATE chat_conversation SET team_id=connection_id")
    op.execute(
        "UPDATE chat_message m SET team_id=v.connection_id FROM chat_conversation v WHERE v.id=m.conversation_id"
    )
    for table in ("chat_connection", "chat_conversation", "chat_message"):
        op.create_foreign_key(
            f"fk_{table}_team", table, "chat_team", ["team_id"], ["id"], ondelete="RESTRICT"
        )
    op.create_unique_constraint("uq_chat_connection_own_team", "chat_connection", ["team_id"])


def downgrade():
    op.drop_constraint("uq_chat_connection_own_team", "chat_connection", type_="unique")
    for table in ("chat_connection", "chat_conversation", "chat_message"):
        op.drop_constraint(f"fk_{table}_team", table, type_="foreignkey")
        # Não transformar grupo de chat em equipe comercial no downgrade.
        op.execute(sa.text(f"UPDATE {table} SET team_id=NULL"))
        op.create_foreign_key(
            f"fk_{table}_team", table, "team", ["team_id"], ["id"], ondelete="RESTRICT"
        )
    op.drop_table("chat_team_member")
    op.drop_table("chat_team")
