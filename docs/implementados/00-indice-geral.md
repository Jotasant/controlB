# Livro de Implementação do ControlB — Capítulo 0: Sumário Executivo & Arquitetura Global

---

## 1. Visão Geral do Sistema

O **ControlB** é uma plataforma corporativa modular de **Gestão Hospitalar, Almoxarifado, Aquisições, Controladoria Financeira e Faturamento (Procure-to-Pay, Enterprise Inventory, Financial Treasury & Order-to-Cash)**.

O sistema foi desenhado para resolver os maiores gargalos de organizações que lidam com itens críticos (medicamentos, materiais médico-hospitalares, insumos e patrimônio):
* **Fim do descontrole de compras:** Exige justificativa formal, fluxo de aprovação por alçada e cotações concorrentes.
* **Governança absoluta de estoque:** Imutabilidade de saldo, controle de lote/validade, rastreabilidade fiscal por NF-e e conciliação de inventário com cálculo de divergências em tempo real.
* **Gestão Financeira & Tesouraria Integrada:** Contas a Pagar e Receber, extratos e conciliação bancária (OFX/CNAB), fluxo de caixa e classificação estratégica de despesas em CAPEX vs OPEX.
* **Faturamento & Frente de Caixa (PDV):** Vendas, emissão de Notas Fiscais Eletrônicas de Saída (NF-e/NFC-e/NFS-e), cobranças automatizadas via PIX/Boleto e operação ágil de balcão.
* **Integridade transacional:** Multi-tenant estrito com isolamento por organização e trilha de auditoria completa (*Audit Trail*).

---

## 2. Arquitetura de Software e Tecnologias Adotadas

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             CLIENTE WEB (SPA)                            │
│           React 18 + TypeScript + Vite + Vanilla SCSS Design System      │
│                     Layout Persistente (AppLayout SPA)                   │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ Porta 80
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      REVERSE PROXY & GATEWAY (NGINX)                     │
│   • /               -> Frontend Vite (Porta 9090)                        │
│   • /identity/      -> FastAPI Backend (Porta 8000)                      │
│   • /purchasing/    -> FastAPI Backend (Porta 8000)                      │
│   • /inventory/     -> FastAPI Backend (Porta 8000)                      │
│   • /financial/     -> (Próxima Fase) FastAPI Backend (Porta 8000)       │
│   • /billing/       -> (Próxima Fase) FastAPI Backend (Porta 8000)       │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        BACKEND API (PYTHON / FASTAPI)                    │
│   • FastAPI (REST APIs assíncronas e tipadas com Pydantic v2)            │
│   • SQLAlchemy 2.0 (Mapeamento Objeto-Relacional & Domain Repositories)  │
│   • Alembic (Migrações versionadas do Schema de Banco)                   │
│   • Autenticação JWT (OAuth2 Password Flow com Hash Bcrypt)              │
│   • Multi-tenancy Nativo (Isolamento estrito por Organization ID)        │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        BANCO DE DADOS (POSTGRESQL 16)                    │
│   • Tabelas relacionais com chaves primárias UUIDv4                      │
│   • Constraints de Integridade Referencial (FKs com ON DELETE RESTRICT)  │
│   • Tipagem Decimal de alta precisão para Moeda e Estoque                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Matriz de Módulos: Estado Atual vs Roadmap

| Módulo do Sistema | Status Atual | O que foi entregue | O que está no Roadmap Imediato |
| :--- | :---: | :--- | :--- |
| **01. Identidade & RBAC** | 🟢 **100% Entregue** | Auth JWT, Multi-tenant, Usuários, Perfis, Cargos e Matriz de Permissões dinâmicas. | 2FA/MFA e Redefinição de senha por e-mail. |
| **02. Compras (Procure-to-Pay)** | 🟢 **95% Entregue** | SC, Itens dinâmicos, Aprovação por alçada, RFQ, Mapa comparativo, PO, Reposição Ágil. | Alçadas multi-nível e Portal do fornecedor. |
| **03. Estoque & Almoxarifado** | 🟢 **95% Entregue** | Catálogo, SKU automático, Lote/Validade, Kardex, Entrada por NF, Baixas e Conciliação. | Leitor de código de barras/coletor e Inventário cego. |
| **04. Gestão Financeira** | 🚀 **Próxima Fase** | Especificação contábil de Contas a Pagar / Receber e Tesouraria. | Títulos, parcelas, conciliação OFX/CNAB, fluxo de caixa, CAPEX/OPEX e anexos. |
| **05. Faturamento & PDV** | 🚀 **Próxima Fase** | Especificação de Order-to-Cash e Frente de Caixa. | Pedidos de venda, NF-e/NFC-e (SEFAZ), cobranças PIX/Boleto, faturas e Frente de Caixa. |
| **06. Controladoria & Analytics** | 🟠 **Parcial** | Dashboard com KPIs e gráficos de área/pizza em Recharts. | Curva ABC (Pareto), DRE Gerencial e DFC Projetado. |

---

## 4. Índice dos Capítulos do Livro

1. [Capítulo 1: Módulo de Identidade, Autenticação e RBAC](./01-modulo-identidade-rbac.md)
2. [Capítulo 2: Módulo de Compras (Procure-to-Pay)](./02-modulo-compras-procure-to-pay.md)
3. [Capítulo 3: Módulo de Estoque e Almoxarifado](./03-modulo-estoque-almoxarifado.md)
4. [Capítulo 4: Módulo de Gestão Financeira, Tesouraria e Controladoria](./04-modulo-gestao-financeira.md)
5. [Capítulo 5: Módulo de Faturamento, Vendas e Integração PDV](./05-modulo-faturamento.md)
6. [Capítulo 6: Arquitetura Frontend SPA, Nginx e DevOps](./06-arquitetura-frontend-devops.md)
