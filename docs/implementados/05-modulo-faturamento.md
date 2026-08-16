# Livro de Implementação do ControlB — Capítulo 5: Módulo de Faturamento, Vendas e Integração PDV

---

## 1. Contexto & Propósito do Módulo

O módulo **Billing & Revenue (Faturamento & Vendas)** é o motor de geração de receita do ControlB. Ele gerencia todo o ciclo de **Order-to-Cash (O2C)**: desde a captação do pedido comercial ou atendimento ambulatorial/hospitalar, passando pela emissão de faturas e documentos fiscais eletrônicos (NF-e/NFC-e/NFS-e), até a liquidação financeira e operação ágil de Frente de Caixa / PDV.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ PEDIDO DE VENDA │ ──► │     FATURA      │ ──► │  NOTA FISCAL DE │
│    OU PDV       │     │   COMERCIAL     │     │  SAÍDA (SEFAZ)  │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │    COBRANÇA     │ ──► │ CONTAS A RECEBER│
                        │  (BOLETO / PIX) │     │ (FINANCEIRO)    │
                        └─────────────────┘     └─────────────────┘
```

---

## 2. Estrutura Detalhada das Funcionalidades a Implementar

### A. Vendas & Pedidos Comerciais
* **Emissão de Pedidos de Venda (`sales_order`):**
  * Seleção de Cliente / Paciente cadastrado (com validação de CPF/CNPJ e limites de crédito).
  * Tabela de preços diferenciada (Preço Balcão, Convênio Particular, Preço Distribuição, Tabela SUS).
  * Adição dinâmica de itens e serviços, com cálculo automático de descontos por item ou no total do pedido.
  * Baixa automática no saldo físico do Módulo de Almoxarifado após a confirmação do pedido.
* **Estados do Ciclo de Venda:**
  * `draft` (orçamento em elaboração).
  * `approved` (pedido confirmado pelo cliente).
  * `invoiced` (faturado e com NF-e emitida).
  * `delivered` (mercadoria entregue / serviço concluído).
  * `cancelled` (cancelado com estorno de estoque e financeiro).

---

### B. Notas Fiscais de Saída (Fiscal Eletrônico)
* **Emissão de Documentos Fiscais Eletrônicos:**
  * **NF-e (Modelo 55):** Nota Fiscal Eletrônica padrão para venda mercantil de medicamentos, materiais e equipamentos.
  * **NFC-e (Modelo 65):** Nota Fiscal de Consumidor Eletrônica para vendas rápidas no balcão / PDV.
  * **NFS-e (Nota de Serviço):** Faturamento de procedimentos médicos, consultas, diárias hospitalares e exames.
* **Motor de Tributação & Regras Fiscais:**
  * Configuração de CFOP (Código Fiscal de Operações e Prestações).
  * Determinação automática de CST/CSOSN por produto.
  * Cálculo de ICMS, ICMS-ST (Substituição Tributária), IPI, PIS e COFINS.
* **Comunicação com a SEFAZ & Prefeituras:**
  * Assinatura digital com Certificado Digital A1 (`.pfx`).
  * Envio de lote síncrono/assíncrono, consulta de recibo e autorização de uso.
  * Geração do arquivo `.xml` assinado e impressão do DANFE em PDF com código de barras e QR Code.
  * Rotinas de Cancelamento formal dentro do prazo legal e Emissão de Carta de Correção Eletrônica (CC-e).

---

### C. Faturas Comerciais & Contratos
* **Consolidação de Faturas (`commercial_invoice`):**
  * Agrupamento de múltiplos atendimentos, guias ou pedidos de venda de um mesmo cliente/convênio em uma fatura única mensal.
  * Detalhamento de itens, procedimentos, taxas hospitalares e materiais de alto custo consumidos.
* **Faturamento de Convênios & Operadoras:**
  * Emissão de faturas estruturadas no padrão **TISS** (Troca de Informações na Saúde Suplementar) e tabelas **TUSS / CBHPM** para operadoras de planos de saúde.

---

### D. Cobranças Inteligentes (Boletos & PIX Dinâmico)
* **Emissão Integrada de Cobranças:**
  * **PIX Dinâmico (Banco Central):** Geração de QR Code instantâneo com valor exato, expiração programada e identificador único (*EndToEndID*).
  * **Boleto Bancário Híbrido:** Boleto tradicional com código de barras FEBRABAN acompanhado de QR Code PIX para pagamento instantâneo.
* **Webhooks de Liquidação Automática:**
  * Notificações em tempo real enviadas pelo banco/gateway assim que o cliente efetua o pagamento.
  * Baixa automática do título a receber no Módulo Financeiro em menos de 3 segundos, sem necessidade de processamento manual de arquivos de retorno.

---

### E. Gestão de Receitas & Reconhecimento Contábil
* **Regime de Competência vs Regime de Caixa:**
  * Reconhecimento da Receita Bruta no momento da entrega do produto ou prestação do serviço (Competência), independentemente da data em que a parcela do cliente será paga (Caixa).
* **Painéis de Análise de Receita:**
  * Faturamento bruto diário, semanal e mensal.
  * Ticket médio por cliente/atendimento.
  * Segmentação de receitas por Categoria de Produto, Departamento e Especialidade Médica.

---

### F. Módulo de Frente de Caixa / PDV (Ponto de Venda)
* **Operação Ágil de Balcão (Farmácia Hospitalar / Loja / Atendimento Rápido):**
  * Interface otimizada para operação rápida via teclado ou tela sensível ao toque (*Touchscreen*).
  * Suporte a leitor de código de barras USB/Bluetooth (bipagem contínua de EAN-13).
* **Controle de Turno de Caixa:**
  * **Abertura de Caixa:** Registro do valor inicial de troco (*Fundo de Caixa / Suprimento*).
  * **Sangria de Caixa:** Retirada segura de valores em dinheiro durante o expediente para envio ao cofre da Tesouraria.
  * **Fechamento de Caixa:** Conferência cega dos valores recebidos em Dinheiro, Cartão de Crédito/Débito, PIX e Convênio, gerando o relatório de fechamento de turno e divergências.
* **Impressão Térmica de Cupom Não Fiscal / NFC-e:**
  * Compatibilidade com impressoras térmicas ESC/POS (Epson, Daruma, Bematech, Elgin de 80mm e 58mm).

---

## 3. Modelo de Dados Previsto (Entidades Principais)

1. **`customer`:** ID, Organization ID, Razão Social / Nome, CPF / CNPJ, Inscrição Estadual, Endereço Completo, Contato, Limite de Crédito.
2. **`sales_order`:** ID, Organization ID, Customer ID, Vendedor / Atendente ID, Data do Pedido, Valor Bruto, Desconto, Valor Líquido, Status (`draft`, `approved`, `invoiced`, `delivered`, `cancelled`).
3. **`sales_order_item`:** ID, Sales Order ID, Product ID, Quantidade, Preço Unitário Tabela, Desconto Aplicado, Preço Final, CFOP, Alíquotas Fiscais.
4. **`fiscal_document_out`:** ID, Organization ID, Sales Order ID / Fatura ID, Modelo (`55_nfe`, `65_nfce`, `nfse`), Série, Número, Chave de Acesso (44 dígitos), XML Assinado, Protocolo de Autorização SEFAZ, Status (`pending`, `authorized`, `cancelled`, `rejected`).
5. **`billing_invoice`:** ID, Organization ID, Customer ID, Número da Fatura, Data de Emissão, Vencimento, Valor Total, Condição de Pagamento.
6. **`charge`:** ID, Organization ID, Fatura / Pedido ID, Meio (`pix`, `boleto`, `card`, `cash`), Código Linha Digitável, QRCode PIX / Imagem, Chave Externa Gateway, Status (`pending`, `paid`, `expired`, `refunded`).
7. **`pos_terminal`:** ID, Organization ID, Nome do Terminal (ex: *Caixa 01 - Farmácia Central*), Mac Address / Identificador, Status Ativo.
8. **`pos_shift`:** ID, POS Terminal ID, Operador User ID, Data Abertura, Fundo Inicial, Data Fechamento, Total Dinheiro, Total Cartões, Total PIX, Divergência Fechamento, Status (`open`, `closed`).
9. **`pos_cash_movement`:** ID, POS Shift ID, Tipo (`suprimento`, `sangria`), Valor, Justificativa, Autorizador ID.
