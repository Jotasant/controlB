# ADR-0003 — Notas e atividades do CRM

Status: aceito

Data: 2026-08-23

## Contexto

O wizard da oportunidade apresenta notas e follow-ups na mesma timeline, mas os dois registros possuem comportamentos diferentes. Uma nota documenta algo que aconteceu; uma atividade representa algo que deve ser executado e acompanhado.

## Opções consideradas

- Tratar todos os registros como texto concluído.
- Criar tabelas totalmente independentes para cada tipo.
- Manter uma abstração comum de interação, com ciclo de vida apenas para atividades.

## Decisão

Notas e atividades podem compartilhar a timeline e a identidade básica, mas possuem semântica explícita:

- Nota: registro histórico sem prazo e sem status de execução.
- Atividade: possui data prevista, responsável e status `SCHEDULED`, `COMPLETED` ou `CANCELLED`.

Ambas podem ser editadas por meio de uma operação auditada. A API deve registrar `updated_at`, autor da alteração e respeitar organização, autoria e permissões de gestão.

## Consequências

- A interface deixa de marcar toda interação automaticamente como concluída.
- Filtros de atrasadas, hoje, futuras e concluídas passam a usar status real.
- A oportunidade terá notas próprias; notas do lead não serão usadas como armazenamento indireto.
- Edições relevantes devem aparecer na auditoria sem apagar o conteúdo anterior silenciosamente.

## Critérios para revisar

Revisar se surgirem recorrência, participantes, lembretes ou dependências que justifiquem um agregado de agenda separado.
