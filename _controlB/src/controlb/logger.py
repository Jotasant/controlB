"""
logger.py - Sistema de Logs Centralizado e Configurável via logging.conf (ControlB)

Responsabilidades:
1. Carregar as configurações declarativas a partir do arquivo 'logging.conf'.
2. Garantir a criação da pasta 'logs/' e do arquivo 'logs/controlb.log'.
3. Capturar todo o tráfego HTTP, exceções não tratadas, auditoria de ações e queries.
"""

import os
import sys
import logging
import logging.config
from controlb.config import ROOT_DIR

# 1. Caminho dos logs e do arquivo de configuração
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "controlb.log")
LOG_CONF_PATH = os.path.join(ROOT_DIR, "logging.conf")

# Garante que o diretório logs/ exista antes de iniciar o handler
os.makedirs(LOGS_DIR, exist_ok=True)


def init_logging() -> logging.Logger:
    """
    Inicializa a infraestrutura de logging:
    - Se logging.conf existir, carrega via logging.config.fileConfig.
    - Se não existir, configura via RotatingFileHandler com fallback robusto.
    """
    if os.path.exists(LOG_CONF_PATH):
        try:
            # Altera o diretório de execução temporariamente se necessário para paths relativos
            logging.config.fileConfig(
                LOG_CONF_PATH,
                disable_existing_loggers=False,
                defaults={"logfilename": LOG_FILE_PATH}
            )
            app_logger = logging.getLogger("controlb")
            app_logger.info(f"📋 Logging inicializado com sucesso a partir de '{LOG_CONF_PATH}'")
            return app_logger
        except Exception as err:
            sys.stderr.write(f"Aviso: Falha ao carregar logging.conf ({err}). Usando configuração padrão.\n")

    # Configuração Padrão de Fallback
    fallback_logger = logging.getLogger("controlb")
    fallback_logger.setLevel(logging.DEBUG)

    if not fallback_logger.hasHandlers():
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)-7s] [%(name)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        from logging.handlers import RotatingFileHandler
        file_h = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_h.setFormatter(formatter)
        file_h.setLevel(logging.DEBUG)
        fallback_logger.addHandler(file_h)

        console_h = logging.StreamHandler(sys.stdout)
        console_h.setFormatter(formatter)
        console_h.setLevel(logging.INFO)
        fallback_logger.addHandler(console_h)

    return fallback_logger


# Instância global do logger
logger = init_logging()
