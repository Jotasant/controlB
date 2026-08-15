# Relatórios e KPIs

## Compras

- Spend por fornecedor, categoria, usuário e centro de custo.
- Lead time por etapa.
- Saving: referência menos preço contratado, com base documentada.
- Compras emergenciais e fora de contrato.

## Fornecedores

- OTIF: entrega completa e no prazo.
- Divergência entre ordem, recebimento e nota.
- Devoluções, atrasos e variação de preço.

## Estoque

- Saldo, giro, cobertura, ruptura e estoque parado.
- Acurácia do inventário.
- Entradas, saídas e ajustes por período/motivo.

## Financeiro e crédito

- Aging de contas a pagar.
- Valor vencido e percentual pago no prazo.
- Caixa projetado por dia/semana.
- Crédito aprovado, comprometido e disponível.
- Orçado versus realizado.

## Governança analítica

Cada indicador deve ter proprietário, fórmula, fonte, granularidade, timezone, filtros, frequência e tratamento de cancelamentos/estornos. O transacional expõe views; consultas pesadas usam materialized views atualizadas e, quando necessário, réplica de leitura.

## Primeiros painéis

1. Operacional: aprovações pendentes, ordens atrasadas, rupturas e títulos próximos do vencimento.
2. Executivo: spend, orçamento, exposição, caixa e tendência.
3. Fornecedor: OTIF, divergência, lead time e preço.
