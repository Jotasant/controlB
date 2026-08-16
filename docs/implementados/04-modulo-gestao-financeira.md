# Livro de Implementação do ControlB — Capítulo 4: Módulo de Gestão Financeira, Tesouraria e Controladoria

---

## 1. Contexto & Propósito do Módulo

O módulo **Financial Management (Gestão Financeira & Tesouraria)** é o centro de controle monetário e contábil do ControlB. Ele centraliza todas as entradas e saídas de recursos, garantindo que o dinheiro da instituição seja gerido com rigor, transparência, conciliação diária e governança contábil.

Ele atua como a ponte integradora entre as **obrigações geradas no Módulo de Compras (Contas a Pagar)** e os **direitos de recebimento gerados no Módulo de Faturamento/Vendas (Contas a Receber)**.

```
┌───────────────────────────┐                       ┌───────────────────────────┐
│     MÓDULO DE COMPRAS     │                       │   MÓDULO DE FATURAMENTO   │
│  (Recebimento Físico NF)  │                       │   (Vendas / Procedimentos)│
└─────────────┬─────────────┘                       └─────────────┬─────────────┘
              │ Gera Obrigação                                    │ Gera Direito
              ▼                                                   ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                          MÓDULO DE GESTÃO FINANCEIRA                          │
│                                                                               │
│  ┌─────────────────────────┐                     ┌─────────────────────────┐  │
│  │     CONTAS A PAGAR      │                     │    CONTAS A RECEBER     │  │
│  │ (Fornecedores/Despesas) │                     │   (Clientes/Convênios)  │  │
│  └────────────┬────────────┘                     └────────────┬────────────┘  │
│               │ Baixa de Pagamento                            │ Recebimento   │
│               ▼                                               ▼               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                      TESOURARIA, CAIXA & BANCOS                         │  │
│  │    • Contas Correntes Bancárias     • Caixas Físicos / Tesouraria       │  │
│  │    • Conciliação de Extratos (OFX)  • Fluxo de Caixa Direto & Projetado │  │
│  │    • Classificação CAPEX / OPEX     • Anexos de Boletos e Comprovantes  │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Estrutura Detalhada das Funcionalidades a Implementar

### A. Contas a Pagar (Payables)
* **Geração Automática de Títulos:** Criados diretamente a partir do recebimento físico e fiscal de Ordens de Compra (PO) no almoxarifado ou lançamentos manuais de despesas fixas (aluguel, água, energia, folha).
* **Plano de Parcelamento:** Desdobramento de títulos em parcelas com prazos comerciais (ex: *30/60/90 DDL*, *14/28 DDL* ou *À Vista*).
* **Gestão de Acréscimos e Descontos:** Lançamento de juros de mora, multas por atraso e descontos por pontualidade/antecipação.
* **Retenções Tributárias na Fonte:** Destacamento e controle de impostos retidos na contratação de serviços e insumos:
  * Federais: PIS, COFINS, CSLL (PCC) e IRRF.
  * Municipais: ISSQN Retido.
* **Autorização de Pagamentos:** Alçada e liberação formal de lotes de pagamento antes da efetivação bancária.

---

### B. Contas a Receber (Receivables)
* **Geração de Títulos a Receber:** Alimentado automaticamente pelo faturamento de vendas, prestação de serviços médicos e faturas de convênios/planos de saúde.
* **Controle de Inadimplência e Régua de Cobrança:**
  * Segmentação de títulos por idade: *A Vencer*, *Vencendo Hoje*, *Vencidos de 1 a 30 dias*, *31 a 60 dias*, *> 60 dias*.
  * Histórico de contatos e renegociação de dívidas com geração de novos acordos e parcelamentos.
* **Baixa de Recebimentos:** Suporte a recebimentos parciais, liquidação total, conciliação de taxas de operadoras de cartão e estornos auditados.

---

### C. Tesouraria & Contas de Caixa
* **Múltiplas Contas Financeiras:** Cadastro e gestão de Contas Correntes Bancárias (Itaú, Bradesco, Banco do Brasil, Santander, etc.), Contas Digitais e Caixas Físicos Internos (Cofre da Tesouraria).
* **Transferências entre Contas:** Movimentações internas entre contas bancárias e suprimentos/recolhimentos de caixas físicos com rastreabilidade dupla (débito na origem / crédito no destino).
* **Saldo em Tempo Real:** Visualização consolidada de saldos disponíveis, bloqueados e projetados.

---

### D. Conciliação Bancária Automatizada
* **Importação de Extratos Eletrônicos:**
  * Suporte a arquivos no formato **OFX** (padrão universal dos bancos).
  * Suporte a arquivos de remessa e retorno **CNAB 240 / CNAB 400**.
* **Motor de Matching Inteligente:**
  * Cruzamento automático entre as transações do extrato e os lançamentos do Contas a Pagar/Receber por data, valor e documento.
  * Painel de conciliação assistida para transações não conciliadas automaticamente com opção de categorização direta de tarifas e rendimentos.

---

### E. Fluxo de Caixa & Controladoria
* **Demonstrativo de Fluxo de Caixa (DFC):**
  * **Fluxo de Caixa Realizado:** Entradas e saídas efetivamente liquidadas nas contas financeiras no período selecionado.
  * **Fluxo de Caixa Projetado (D+30, D+60, D+90):** Projeção futura com base nos títulos a pagar e a receber em aberto, prevendo necessidades de capital de giro ou sobras financeiras para aplicação.
* **DRE Gerencial (Demonstrativo do Resultado do Exercício):** Visão contábil por regime de competência apurando Receita Bruta, Deduções, Custo de Mercadorias Vendidas (CMV), Despesas Operacionais e Lucro Líquido.

---

### F. Classificação Estratégica CAPEX vs OPEX
* Todo lançamento financeiro e requisição de compra passará a contar com a classificação contábil mandatória:
  * **CAPEX (*Capital Expenditure* - Bens de Capital):** Aquisição de máquinas, tomógrafos, leitos hospitalares, equipamentos de TI e benfeitorias estruturais com plano de depreciação e tombamento patrimonial.
  * **OPEX (*Operational Expenditure* - Despesas Operacionais):** Despesas do dia a dia necessárias para a manutenção das operações (medicamentos, insumos de limpeza, água, energia, salários).
* **Painel Executivo CAPEX/OPEX:** Relatórios gráficos demonstrando a distribuição dos gastos da organização entre investimento em infraestrutura e custos correntes de operação.

---

### G. Central de Documentos Financeiros (Anexos & Auditoria)
* **Boletos Bancários:** Armazenamento de arquivos PDF e extração de código de barras/linha digitável e link de pagamento.
* **Comprovantes de Pagamento e Recebimento:** Upload de PDFs/imagens dos comprovantes de TED, DOC, PIX e transferências emitidos pelos bancos.
* **Extratos Consolidados:** Guarda mensal de extratos bancários conciliados para auditoria fiscal e contábil.
* **Imutabilidade e Segurança:** Arquivos protegidos com hash de integridade (SHA-256) e permissão de visualização restrita por RBAC (`financial:docs:view`).

---

## 3. Modelo de Dados Previsto (Entidades Principais)

1. **`bank_account`:** ID, Organization ID, Nome do Banco, Código Febraban, Agência, Conta Corrente, Saldo Atual, Status Ativo.
2. **`payable_title`:** ID, Organization ID, Fornecedor ID, Centro de Custo ID, Categoria ID, Classificação (CAPEX/OPEX), Número da NF, Valor Nominal, Valor Pago, Status (`open`, `partially_paid`, `paid`, `cancelled`).
3. **`payable_installment`:** ID, Payable Title ID, Número da Parcela, Data de Vencimento, Valor Parcela, Linha Digitável / PIX, Acréscimos, Descontos, Data do Pagamento, Status.
4. **`receivable_title`:** ID, Organization ID, Cliente/Paciente ID, Fatura ID, Valor Nominal, Valor Recebido, Vencimento, Status (`open`, `received`, `overdue`, `cancelled`).
5. **`financial_transaction`:** ID, Organization ID, Bank Account ID, Tipo (`credit`/`debit`), Valor, Data da Transação, Categoria, Documento ID, Vinculação com Título, Status da Conciliação.
6. **`bank_statement_import`:** ID, Organization ID, Bank Account ID, Arquivo OFX/CNAB, Data da Importação, Total de Linhas Conciliadas.
7. **`financial_attachment`:** ID, Organization ID, Transação/Título ID, Tipo (`boleto`, `receipt`, `statement`, `invoice`), URL/Path do Arquivo, Hash SHA-256.
