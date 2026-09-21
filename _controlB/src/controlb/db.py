"""
db.py - Configuração de Conexão com o Banco de Dados (SQLAlchemy ORM)

Responsabilidades:
1. Definir a classe 'Base' para mapeamento de tabelas (Declarative Base).
2. Criar a 'Engine' de conexão do SQLAlchemy com pooling e verificação ativa.
3. Criar a fábrica de sessões 'SessionLocal'.
4. Fornecer a função geradora 'get_db()' para injeção de dependência no FastAPI.
"""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from controlb.config import get_settings


class Base(DeclarativeBase):
    """
    Classe base para todos os modelos ORM (tabelas do banco de dados).
    Todas as classes que herdam de 'Base' (User, Role, Organization) são
    automaticamente registradas pelo SQLAlchemy para criação de tabelas e migrações.
    """
    pass


# Obtém as configurações validadas (URL do banco, ambiente, etc.)
settings = get_settings()

# Engine: O motor principal que gerencia o pool de conexões com o PostgreSQL
engine = create_engine(
    settings.database_url,
    hide_parameters=True,                  # Não registrar mensagens, anexos ou credenciais nos parâmetros SQL.
    pool_pre_ping=True,                     # Testa a conexão antes de usá-la, evitando quedas por timeout
    echo=settings.app_env == "development", # Em desenvolvimento, exibe todas as queries SQL no terminal
)

# SessionLocal: Fábrica que gera sessões individuais com o banco para cada requisição
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,        # Não envia alterações automáticas pro banco antes de consultas explícitas
    expire_on_commit=False, # Impede que objetos fiquem inacessíveis após um commit
)


def get_db() -> Generator[Session, None, None]:
    """
    Injeção de Dependência para o FastAPI.
    Abre uma sessão de banco de dados para a requisição HTTP e garante seu fechamento
    automático ('finally') após a resposta ser enviada, prevenindo vazamento de conexões.
    """
    with SessionLocal() as session:
        try:
            yield session
            # A requisição HTTP é a fronteira transacional padrão. Serviços novos
            # devem usar add/flush e deixar este ponto confirmar o caso de uso inteiro.
            session.commit()
        except Exception:
            session.rollback()
            raise
