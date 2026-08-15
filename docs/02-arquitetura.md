# Arquitetura e tecnologias

## Estratégia

Adotar um monólito modular, implantado como uma unidade, com limites claros entre identidade, compras, estoque, financeiro, crédito e relatórios. Serviços separados só serão considerados por necessidade comprovada de escala, isolamento ou autonomia de equipe.

## Stack inicial

| Área | Tecnologia | Justificativa |
|---|---|---|
| Banco | PostgreSQL 17 em Docker Compose | Transações, constraints, JSONB e ecossistema de BI |
| Backend | Python 3.12+ e FastAPI | Tipagem, produtividade e OpenAPI |
| ORM | SQLAlchemy 2 síncrono | Maturidade e controle explícito de transações |
| Migrações | Alembic | Evolução reproduzível do esquema |
| Driver | psycopg 3 | Integração atual com PostgreSQL |
| Frontend | React, TypeScript e Vite | Telas operacionais e ecossistema consolidado |
| Arquivos | S3 compatível; MinIO local | Objetos privados fora do banco |
| Jobs | Scheduler simples no MVP | Alertas sem infraestrutura prematura |
| BI | Views PostgreSQL e Metabase | Entrega rápida e baixo acoplamento |
| Qualidade | pytest, Ruff, mypy e pre-commit | Feedback automatizado |

## Limites dos módulos

```text
identity     usuários, perfis, autenticação e autorização
purchasing   solicitações, cotações, aprovações e ordens
inventory    recebimentos, movimentos, saldos e inventários
payables     títulos, parcelas, pagamentos e comprovantes
credit       orçamento, limites, reservas e projeções
reporting    consultas, KPIs e exportações
shared       auditoria, arquivos, eventos e erros comuns
```

Rotas tratam transporte; casos de uso coordenam regras e transações; domínio expressa invariantes; repositórios isolam persistência. Modelos ORM não devem ser retornados diretamente pela API.

## Integrações e confiabilidade

- Usar timeout, retry com backoff e idempotência.
- Publicar eventos externos via outbox transacional.
- Armazenar anexos em bucket privado, mantendo checksum e metadados no banco.
- Processos agendados devem registrar tentativas e impedir alertas duplicados.

## Evolução

Escalar primeiro com múltiplos workers, índices, cache seletivo e consultas analíticas separadas. Avaliar filas, réplica de leitura, particionamento e extração de serviços somente após medir gargalos.
