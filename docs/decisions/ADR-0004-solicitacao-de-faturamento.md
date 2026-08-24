# ADR-0004 — Solicitação de faturamento

Status: aceito

Data: 2026-08-23

## Contexto

O módulo Vendas deve controlar o pedido, enquanto Faturamento valida e emite os documentos fiscais. Atualmente, a operação chamada “solicitar faturamento” cria imediatamente uma fatura e os recebíveis financeiros.

## Opções consideradas

- Vendas emitir diretamente a fatura.
- Vendas criar uma solicitação processada pelo módulo de Faturamento.
- Usar apenas um status textual no pedido, sem entidade intermediária.

## Decisão

Vendas criará uma solicitação de faturamento auditável. O módulo Faturamento será responsável por aprovar, rejeitar ou emitir a fatura.

A solicitação deverá suportar quantidades por item para permitir faturamento parcial sem duplicar o pedido.

## Consequências

- `REQUESTED` não significa `INVOICED`.
- A criação de recebíveis ocorre somente após emissão pelo Faturamento.
- Pedido, solicitação e fatura permanecem ligados na cadeia documental.
- A implementação atual de emissão imediata será substituída em uma etapa posterior com migração e testes próprios.

## Critérios para revisar

Revisar apenas se o produto operar em um cenário sem separação fiscal, no qual o mesmo ator seja formalmente responsável por venda e emissão.
