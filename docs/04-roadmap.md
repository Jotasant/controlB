# Roadmap

As durações são referências para priorização, não compromissos fixos.

## Fase 0 — fundação (1 semana)

- Repositório, convenções, ambientes e Docker Compose.
- Projeto Python, PostgreSQL, SQLAlchemy e Alembic.
- CI, lint, testes, configuração e gestão de segredos.
- Autenticação, RBAC e base de auditoria.

Saída: ambiente reproduzível e primeira migração validada.

## Fase 1 — compras (2–3 semanas)

- Cadastros essenciais.
- Solicitação, aprovação por alçada e ordem de compra.
- Histórico de estados e cancelamento controlado.

Saída: uma compra aprovada pode virar ordem auditável.

## Fase 2 — recebimento e estoque (2–3 semanas)

- Recebimentos parciais e divergências.
- Nota fiscal e conferência pedido × recebimento × nota.
- Entradas, saídas, ajustes e consulta de saldo.

Saída: estoque rastreável e protegido contra duplicidade.

## Fase 3 — financeiro (2–3 semanas)

- Títulos, parcelas, pagamentos parciais/totais e estornos.
- Comprovantes privados e alertas de vencimento.
- Aging e calendário financeiro.

Saída: dívida rastreável até compra, nota e comprovante.

## Fase 4 — orçamento e inteligência (2 semanas)

- Limites, reservas e exposição de crédito.
- Melhor data de compra e projeção de caixa.
- Painéis e views analíticas.

## Fase 5 — robustez e integrações (contínua)

- Importação de NF-e, bancos, cartões e ERP.
- Testes de carga, observabilidade e recuperação de desastre.
- Réplica de leitura ou particionamento quando as métricas justificarem.

## Definition of Done

Regra aceita pelo usuário, código revisado, testes relevantes, migração segura, autorização verificada, auditoria/logs, documentação atualizada e plano de rollback.
