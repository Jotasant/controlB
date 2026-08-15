# Modelo de dados e regras

## Agregados principais

- Organização: `organization`, `user`, `role`, `cost_center`, `warehouse`.
- Catálogo: `supplier`, `category`, `product`.
- Compras: `purchase_request`, `quotation`, `purchase_order`, itens e eventos de aprovação.
- Recebimento: `receipt`, itens, divergências e `fiscal_document`.
- Estoque: `stock_movement`, reserva e inventário.
- Financeiro: `payable`, `installment`, `payment`, estorno e `attachment`.
- Controle: `budget`, `credit_limit`, `credit_reservation`, `notification`, `audit_event`, `outbox_event`.

## Relacionamento central

```text
solicitação -> aprovação -> ordem -> recebimento -> movimento de estoque
                                  -> nota fiscal -> título -> pagamento
```

Uma ordem pode ter vários recebimentos e uma conta pode ter várias parcelas e pagamentos.

## Invariantes

- Valores monetários usam `NUMERIC`; nunca `float`.
- Quantidades usam precisão definida por unidade.
- Datas financeiras e eventos usam timezone; vencimento usa data civil.
- Estoque é um livro imutável: correções geram movimentos compensatórios.
- Pagamento não pode superar o saldo sem regra explícita de crédito.
- Recebimento acumulado não pode superar a quantidade pedida sem autorização.
- Chave de NF-e deve ser única por emissor.
- Operações repetíveis recebem chave idempotente única.
- Exclusão lógica não substitui trilha de auditoria.
- FKs, uniques e checks reforçam invariantes no banco.

## Estados sugeridos

Ordem: `draft`, `pending_approval`, `approved`, `partially_received`, `received`, `closed`, `cancelled`.

Título: `open`, `partially_paid`, `paid`, `overdue`, `cancelled`.

## Concorrência

Recebimento, reserva de limite e baixa financeira devem ocorrer em transações curtas. Bloqueio pessimista ou atualização condicional será usado apenas nos registros disputados. Toda repetição por timeout deve ser segura por idempotência.

## Auditoria

Registrar ator, instante, organização, ação, entidade, identificador, correlação, origem e antes/depois permitido. Eventos financeiros e de estoque não devem ser apagados.
