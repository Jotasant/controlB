"""
main.py - Ponto de Entrada Principal da Aplicação FastAPI (ControlB)

Responsabilidades:
1. Instanciar o aplicativo FastAPI com metadados (título, versão).
2. Configurar os middlewares de segurança e comunicação entre domínios (CORS).
3. Registrar rotas básicas da raiz ('/') e de checagem de saúde ('/health').
4. Incluir e registrar os roteadores modulares (ex: módulo de Identity).
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from controlb.config import get_settings
from controlb.db import get_db
from controlb.modules.identity.api import router as identity_router
from controlb.modules.purchasing.api import router as purchasing_router

# Carrega as configurações centralizadas
settings = get_settings()

# 1. Instanciação da aplicação FastAPI
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API do ecossistema ControlB para compras, estoque, financeiro e indicadores.",
)

# 2. Configuração do Middleware de CORS (Cross-Origin Resource Sharing):
# Permite que o frontend (rodando em outra porta ou IP) faça requisições HTTP seguras para esta API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # Em produção, restringe-se aos domínios autorizados (ex: https://meusistema.com)
    allow_credentials=True,  # Permite envio de cookies e headers de autorização
    allow_methods=["*"],      # Permite todos os métodos HTTP (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],      # Permite todos os cabeçalhos (como Authorization e Content-Type)
)

# 3. Rota Raiz ('/'): Retorna o status geral e o nome do serviço
@app.get("/")
def root() -> dict[str, str]:
    """Retorna metadados básicos confirmando que o backend está online."""
    return {
        "service": settings.app_name,
        "status": "running",
    }

# 4. Rota de Healthcheck ('/health'): Testa a conexão ativa com o banco PostgreSQL
@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Executa uma consulta simples 'SELECT 1' no banco de dados para validar
    se a aplicação consegue se comunicar com o PostgreSQL com sucesso.
    """
    db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
    }

# 5. Registro de Roteadores Modulares:
# Conecta todos os endpoints de Identity (usuários, auth) e Purchasing (compras, catálogo)
app.include_router(identity_router)
app.include_router(purchasing_router)
