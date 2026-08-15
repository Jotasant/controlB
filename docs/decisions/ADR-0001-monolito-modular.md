# ADR-0001 — Monólito modular

Status: aceito

Data: 2026-08-01

## Contexto

O produto reúne domínios relacionados, está no início e precisa evoluir rapidamente sem multiplicar implantação, observabilidade e consistência distribuída.

## Opções consideradas

- Monólito sem limites formais.
- Monólito modular.
- Microsserviços desde o início.

## Decisão

Usar monólito modular com módulos de negócio explícitos, um banco PostgreSQL e uma unidade de implantação.

## Consequências

Transações e operação permanecem simples. A equipe deve proteger os limites entre módulos para evitar acoplamento. Extração futura exigirá contratos e eventos bem definidos.

## Critérios para revisar

Necessidade comprovada de escala independente, isolamento regulatório, disponibilidade distinta ou equipes autônomas por domínio.
