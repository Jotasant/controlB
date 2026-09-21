"""
config.py - Gerenciamento Centralizado de Configurações e Variáveis de Ambiente

Utiliza o Pydantic Settings para carregar, validar e tipar todas as configurações
definidas no arquivo .env (como credenciais de banco de dados, segredos JWT e portas).
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. Localização dinâmica do caminho da raiz do projeto e do arquivo .env
# __file__ -> src/controlb/config.py
# dirname 1 -> src/controlb
# dirname 2 -> src
# dirname 3 -> _controlB (onde fica o .env)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE_PATH = os.path.join(ROOT_DIR, ".env")


class Settings(BaseSettings):
    """
    Classe de configurações da aplicação validada pelo Pydantic.
    Se uma variável obrigatória (como database_url ou secret_key) faltar no .env,
    a aplicação dispara um erro imediatamente ao inicializar.
    """
    # Nome e Ambiente da Aplicação
    app_name: str = "ControlB API"
    app_env: str = "development"

    # URL de Conexão com o Banco PostgreSQL (ex: postgresql+psycopg://user:pass@localhost:5433/db)
    database_url: str

    # Configurações de Segurança do Token JWT
    secret_key: str                     # Chave secreta usada para assinar digitalmente os tokens JWT
    algorithm: str = "HS256"            # Algoritmo de criptografia do token (HMAC com SHA-256)
    access_token_expire_minutes: int = 480 # Tempo de expiração da sessão do usuário (em minutos)

    # Chave dedicada para credenciais de conectores. Quando não informada, a
    # SECRET_KEY existente é usada como origem de chave para manter compatibilidade.
    chat_credentials_key: str | None = None
    chat_public_base_url: str | None = None
    # URLs exatas aprovadas pelo operador para evitar chamadas a destinos arbitrários.
    chat_allowed_base_urls: list[str] = []
    # STT opcional/local. Nenhum modelo é baixado e nenhum áudio é enviado a terceiros.
    chat_stt_model_path: str | None = None
    chat_audio_worker_enabled: bool = True

    # Configuração do Pydantic para ler do arquivo .env
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        extra="ignore",                 # Ignora variáveis extras presentes no .env sem dar erro
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna a instância única (Singleton) das configurações.
    O decorator @lru_cache() garante que o arquivo .env seja lido apenas uma vez na memória,
    evitando leituras repetidas de disco a cada requisição.
    """
    return Settings()
