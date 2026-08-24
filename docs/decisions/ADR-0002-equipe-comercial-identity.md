# ADR-0002 — Equipe comercial compartilhada no Identity

Status: aceito

Data: 2026-08-23

## Contexto

CRM acompanha a negociação e Vendas executa o que foi vendido. Os dois módulos precisam usar a mesma equipe comercial, sem duplicar membros, liderança ou regras de visibilidade.

O módulo Identity já possui `Team`, membros, líder e categoria. Criar `CRMTeam` ou `SalesTeam` produziria fontes concorrentes para a mesma estrutura organizacional.

## Opções consideradas

- Criar modelos separados de equipe em CRM e Vendas.
- Criar uma categoria diferente para cada módulo.
- Reutilizar `Identity.Team` com a categoria `SALES` representando todo o ciclo comercial.

## Decisão

`Identity.Team` é a fonte única de equipes. A categoria persistida `SALES` representa a equipe Comercial/Vendas e é consumida tanto pelo CRM quanto por Vendas.

CRM não cria uma cópia da equipe. Permissões, liderança, membros e escopo partem do Identity. Nas próximas etapas, oportunidade, cotação e pedido guardarão a referência da equipe responsável para preservar o histórico.

## Consequências

- Uma alteração de membros é feita uma vez no Identity.
- CRM e Vendas compartilham a mesma hierarquia de acesso.
- O código interno continua sendo `SALES`; a interface pode exibir “Comercial/Vendas”.
- A equipe gravada no documento não deve ser recalculada retroativamente quando o vendedor mudar de equipe.
- Endpoints de equipes devem validar tenant e exigir permissão administrativa específica.

## Critérios para revisar

Revisar se uma organização precisar de equipes de pré-vendas e execução completamente independentes, com membros, líderes e escopos distintos.
