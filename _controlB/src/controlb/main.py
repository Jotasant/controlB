"""
main.py - Ponto de Entrada Principal da Aplicação FastAPI (ControlB)

Responsabilidades:
1. Instanciar o aplicativo FastAPI com metadados (título, versão).
2. Configurar os middlewares de segurança (CORS) e de auditoria de logs (controlb.log).
3. Registrar rotas básicas da raiz ('/') e de checagem de saúde ('/health').
4. Incluir e registrar os roteadores modulares (Identity e Purchasing).
5. Tratar e logar 100% de exceções do sistema (4xx, 422 validações, 5xx e tracebacks).
"""

import time
import traceback
from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from controlb.config import get_settings
from controlb.db import get_db
from controlb.logger import logger
from controlb.modules.identity.api import router as identity_router
from controlb.modules.purchasing.api import router as purchasing_router
from controlb.modules.inventory.api import router as inventory_router
from controlb.modules.crm.api import router as crm_router
from controlb.modules.sales.api import router as sales_router
from controlb.modules.billing.api import router as billing_router
from controlb.modules.finance.api import router as finance_router
from controlb.modules.documents.api import router as documents_router
from controlb.modules.projects.api import router as projects_router
from controlb.modules.chat.api import router as chat_router


# Carrega as configurações centralizadas
settings = get_settings()

# 1. Instanciação da aplicação FastAPI
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API do ecossistema ControlB para compras, estoque, CRM, vendas, faturamento, financeiro e projetos & operações.",
)

# 2. Configuração do Middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Middleware Global de Auditoria e Logs de Requisições HTTP
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """
    Registra no arquivo logs/controlb.log todas as requisições recebidas pela API,
    incluindo Método, Rota, IP de Origem, Código de Resposta e Duração em milissegundos.
    """
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    url_path = request.url.path

    logger.info(f"➡️ [HTTP IN] {method} {url_path} - IP: {client_ip}")

    try:
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code

        log_level = logger.warning if status_code >= 400 else logger.info
        log_level(f"⬅️ [HTTP OUT] {method} {url_path} -> Status {status_code} ({process_time_ms:.2f}ms)")
        
        return response
    except Exception as exc:
        process_time_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"❌ [HTTP UNCAUGHT ERROR] {method} {url_path} ({process_time_ms:.2f}ms): {str(exc)}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Erro interno no servidor. Consulte os logs do sistema."}
        )


# 4. Handlers Globais de Exceções para Registro Detalhado nos Logs
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Captura e grava nos logs falhas de validação de schemas Pydantic."""
    errors = exc.errors()
    if request.url.path.startswith("/chat/"):
        # Não registrar valores de entrada: configurações e callbacks contêm segredos.
        safe_errors = [
            {"loc": list(error["loc"]), "type": error["type"], "msg": "Campo inválido."}
            for error in errors
        ]
        return JSONResponse(status_code=422, content={"detail": safe_errors})
    logger.warning(f"⚠️ [VALIDATION ERROR 422] {request.method} {request.url.path} - Erros: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors}
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Captura e grava nos logs respostas HTTP com status de erro (404, 403, 401, 400)."""
    if exc.status_code >= 400:
        logger.warning(f"⚠️ [HTTP {exc.status_code}] {request.method} {request.url.path} - Detalhe: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )


# 5. Rota Raiz ('/'): Retorna o status geral e o nome do serviço
@app.get("/")
def root() -> dict[str, str]:
    """Retorna metadados básicos confirmando que o backend está online."""
    return {
        "service": settings.app_name,
        "status": "running",
    }


# 6. Rota de Healthcheck ('/health'): Testa a conexão ativa com o banco PostgreSQL
@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Valida se a aplicação consegue se comunicar com o PostgreSQL com sucesso."""
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
    }


# 7. Registro de Roteadores Modulares:
app.include_router(identity_router)
app.include_router(inventory_router, prefix="/inventory")
app.include_router(purchasing_router)
app.include_router(crm_router)
app.include_router(sales_router)
app.include_router(billing_router)
app.include_router(finance_router)
app.include_router(documents_router)
app.include_router(projects_router)
app.include_router(chat_router)

logger.info("🚀 Sistema ControlB API inicializado com sucesso e pronto para requisições.")
