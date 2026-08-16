"""
env.py - Script de Execução e Configuração do Alembic (Migrações de Banco de Dados)

Responsabilidades:
1. Conectar o Alembic aos metadados dos modelos SQLAlchemy (Base.metadata).
2. Ler dinamicamente a URL do banco PostgreSQL a partir do config.py / .env.
3. Executar as migrações em modo online (direto no banco ativo) ou offline (gerando script SQL puro).
"""

import logging
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Importações dos modelos do projeto para detecção automática de alterações de schema (autogenerate)
from controlb.db import Base
from controlb.modules.identity.models import Organization, Role, User, Permission
from controlb.modules.inventory.models import ProductCategory, Product, StockMovement
from controlb.modules.purchasing.models import (
    Supplier, CostCenter, 
    PurchaseRequest, PurchaseRequestItem, ApprovalEvent, 
    PurchaseOrder, PurchaseOrderItem,
    QuotationProcess, SupplierQuote, SupplierQuoteItem
)
from controlb.modules.finance.models import (
    FinancialCategory, BankAccount, FiscalDocument,
    Payable, PaymentInstrument, Payment, PaymentAttachment,
    BankTransaction, Reconciliation, Receivable, Receipt, SalesReport
)
from controlb.modules.crm.models import Lead, Opportunity, CustomerInteraction
from controlb.modules.sales.models import (
    SalesQuote, SalesQuoteItem, SalesOrder, SalesOrderItem,
    POSSession, POSSale, POSSaleItem
)
from controlb.modules.billing.models import Invoice, InvoiceInstallment
from controlb.config import get_settings


# Carrega as configurações de logging definidas no alembic.ini
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Informa ao Alembic quais tabelas e colunas existem na aplicação
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Modo Offline: Gera o script SQL das migrações sem precisar de conexão ativa com o banco.
    Útil para auditoria de scripts SQL por DBAs antes de aplicar em produção.
    """
    settings = get_settings()
    url = str(settings.database_url)
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Modo Online: Conecta-se diretamente ao PostgreSQL e aplica as alterações na estrutura das tabelas.
    É o modo executado pelo comando 'alembic upgrade head' no control_start.ps1.
    """
    settings = get_settings()
    
    # Injeta a URL do banco de dados lida do .env pelo config.py dinamicamente no Alembic
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = str(settings.database_url)

    # Cria o pool de conexão para executar as instruções DDL (CREATE TABLE, ALTER TABLE, etc.)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        # Executa as migrações dentro de uma transação segura (se falhar, faz rollback automático)
        with context.begin_transaction():
            context.run_migrations()


# Seleciona o modo de execução apropriado
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
