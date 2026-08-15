# ControlB — guia vivo de desenvolvimento

Planejamento técnico de uma aplicação para compras, estoque, contas a pagar, crédito e indicadores. Nesta fase, o repositório contém somente documentação; o código será criado incrementalmente conforme o roadmap.

## Documentos

- [Visão do produto](docs/01-visao-produto.md)
- [Arquitetura e tecnologias](docs/02-arquitetura.md)
- [Modelo de dados e regras](docs/03-modelo-dados.md)
- [Roadmap](docs/04-roadmap.md)
- [Backlog priorizado](docs/05-backlog.md)
- [Guia de implementação](docs/06-guia-implementacao.md)
- [Qualidade, segurança e operação](docs/07-qualidade-seguranca.md)
- [Relatórios e KPIs](docs/08-relatorios-kpis.md)
- [Ideias de evolução](docs/09-ideias-evolucao.md)
- [Decisões arquiteturais](docs/decisions/README.md)

## Princípios

1. Começar como monólito modular.
2. Preservar rastreabilidade financeira e de estoque.
3. Aplicar regras críticas também no PostgreSQL.
4. Entregar fluxos verticais pequenos e testáveis.
5. Só adicionar infraestrutura quando houver necessidade medida.

## Próximo passo

Validar o escopo do MVP e iniciar a Fase 0 descrita no roadmap.
