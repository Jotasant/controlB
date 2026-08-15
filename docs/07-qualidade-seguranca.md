# Qualidade, segurança e operação

## Testes

- Unitários: regras, estados, limites e cálculos.
- Integração: constraints, transações, consultas e migrações no PostgreSQL real.
- E2E: solicitar → aprovar → receber → pagar.
- Concorrência: recebimento duplicado, baixa simultânea e reserva de crédito.
- Contrato: integrações e OpenAPI.

Priorizar risco e comportamento; cobertura numérica não substitui cenários críticos.

## Segurança

- Senhas com algoritmo resistente e autenticação com expiração/rotação adequada.
- RBAC por organização e segregação de funções.
- Princípio do menor privilégio no banco e storage.
- Comprovantes em bucket privado com URL temporária.
- Validação de tipo, tamanho, malware e checksum de anexos.
- Segredos em cofre/variáveis protegidas, nunca no repositório.
- Rate limit e proteção contra força bruta em autenticação.
- Mascarar dados sensíveis em logs e exportações.

## Observabilidade

Logs JSON com `request_id`, `correlation_id`, usuário e organização; métricas de latência, erro, conexões e filas; tracing em integrações; alertas acionáveis com runbook.

## Banco e continuidade

- Migrações compatíveis com implantação gradual.
- Backups automáticos e recuperação point-in-time.
- Testes periódicos de restauração.
- Índices guiados por consultas reais e `EXPLAIN`.
- Transações curtas e pool dimensionado por instâncias/workers.

## CI/CD

Pipeline mínimo: lint, tipos, testes unitários, testes de integração, verificação de migrações, análise de dependências e build imutável. Produção exige aprovação e rollback documentado.
