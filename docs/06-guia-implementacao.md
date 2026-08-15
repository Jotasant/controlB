# Guia de implementação

## Ponto de partida

1. Confirmar o recorte do MVP e termos do domínio.
2. Criar `compose.yaml` com PostgreSQL e healthcheck.
3. Iniciar Python 3.12+, FastAPI, SQLAlchemy 2, psycopg e Alembic.
4. Configurar lint, tipos, testes, pre-commit e CI.
5. Implementar organização, usuário, RBAC e auditoria.
6. Entregar um fluxo vertical: solicitação simples do banco até a API.
7. Evoluir pelo roadmap, uma migração e um caso de uso por vez.

## Estrutura alvo

```text
src/controlb/
  modules/
    identity/{api,application,domain,infrastructure}/
    purchasing/{api,application,domain,infrastructure}/
    inventory/{api,application,domain,infrastructure}/
    payables/{api,application,domain,infrastructure}/
    credit/{api,application,domain,infrastructure}/
    reporting/
  shared/{audit,events,files,errors}/
  config.py
  db.py
  main.py
alembic/
tests/{unit,integration,e2e}/
```

## Fluxo de uma entrega

- Escrever regra e exemplos de aceitação.
- Modelar estados e invariantes antes da rota.
- Criar migração Alembic revisável e reversível quando possível.
- Implementar caso de uso com fronteira transacional explícita.
- Cobrir regra em teste unitário e persistência em integração.
- Validar autorização, auditoria, erros e idempotência.
- Atualizar OpenAPI e documentação do domínio.

## Regras de engenharia

- Uma sessão SQLAlchemy por request ou job; nunca compartilhá-la entre threads.
- Não usar `create_all()` em produção.
- Não esconder commits dentro de repositórios; o caso de uso controla a transação.
- Evitar dependências entre módulos por acesso direto às tabelas; usar contratos internos.
- Paginar movimentos e auditoria por cursor.
- Não armazenar arquivos binários grandes no PostgreSQL.
- Toda integração externa deve aceitar reprocessamento seguro.

## Ambientes

Desenvolvimento local via Docker; testes com banco descartável; homologação semelhante à produção. Segredos ficam fora do Git e configurações são validadas na inicialização.
