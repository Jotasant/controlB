# Livro de Implementação do ControlB — Capítulo 2: Módulo de Compras (Procure-to-Pay)

---

## 1. Contexto & Propósito do Módulo

O módulo **Purchasing (Compras & Suprimentos)** gerencia todo o ciclo de vida de aquisições da organização, desde a necessidade identificada na ponta até a emissão formal do pedido de compra.

O fluxo cobre integralmente o processo de **Procure-to-Pay (P2P)**:
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  SOLICITAÇÃO    │ ──► │    APROVAÇÃO    │ ──► │    COTAÇÃO      │
│  DE COMPRA (SC) │     │   POR ALÇADA    │     │   (RFQ / MAPA)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  RECEBIMENTO NO │ ◄── │  ORDEM DE COMPRA│ ◄── │  HOMOLOGAÇÃO    │
│  ALMOXARIFADO   │     │   OFICIAL (PO)  │     │   DO VENCEDOR   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 2. O que foi Implementado (100% Entregue)

### A. Cadastros de Apoio & Estrutura Comercial
* **Fornecedores Homologados ([`Supplier`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/purchasing/models.py)):** Razão Social, Nome Fantasia, CNPJ/CPF, Inscrição Estadual, Vendedor de Contato, E-mail, Telefone, Segmentos de Atuação, Condição de Pagamento Padrão (ex: *30 DDL*), Valor Mínimo de Pedido e Licença Sanitária ANVISA / AFE.
* **Centros de Custo ([`CostCenter`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/purchasing/models.py)):** Código Operacional/Contábil (ex: `CC-FARM-01`), Nome do Departamento e Gestor Responsável.

### B. Solicitações de Compra (PR - Purchase Request)
* **Emissão com Múltiplos Itens:** Criação dinâmica de itens com busca direta no catálogo, seleção de produto, quantidade solicitada, preço unitário estimado e observações técnicas.
* **Numeração Sequencial Inteligente:** Geração automática e amigável no formato `SC-YYYY-XXXX` (ex: `SC-2026-0001`).
* **Estados do Ciclo de Vida:** `draft` (rascunho), `pending_approval` (aguardando gestor), `approved` (aprovada), `rejected` (recusada) e `cancelled` (cancelada).
* **Rotina de Exclusão Segura & Purga:** Permite a remoção de solicitações individuais (com desvinculação limpa de ordens) ou purga em lote para ambiente de desenvolvimento.

### C. Workflow de Aprovação por Alçada
* **Histórico Formal de Decisão ([`ApprovalEvent`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/purchasing/models.py)):** Grava o ID do aprovador (`approver_id`), carimbo de data/hora, status (`approved`/`rejected`) e parecer/justificativa formal do gestor.

### D. Processos de Cotação (RFQ - Request For Quotation) & Propostas
* **Abertura de Cotação:** Conversão de uma solicitação aprovada em um processo de RFQ oficial (`COT-YYYY-XXXX`).
* **Propostas Comerciais Concorrentes ([`SupplierQuote`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/purchasing/models.py)):** Lançamento de propostas de múltiplos fornecedores para os mesmos itens, com prazo de pagamento, tipo de frete (CIF/FOB), valor de frete, desconto comercial, prazo de entrega em dias (*lead time*) e validade da proposta.
* **Mapa Comparativo de Cotações:** Matriz em tempo real que analisa produto a produto qual fornecedor ofertou o menor preço e destaca a economia global alcançada.
* **Homologação e Conversão em PO:** Ao escolher a proposta vencedora, o sistema marca a cotação como concluída e emite a Ordem de Compra oficial automaticamente.

### E. Ordens de Compra Oficiais (PO - Purchase Order)
* **Emissão Oficial (`OC-YYYY-XXXX`):** Itens negociados, preços finais, condições contratuais, cálculo automático de frete e desconto líquido.
* **Estados da Ordem:** `draft`, `issued` (emitida/enviada), `partially_received` (recebimento parcial), `received` (concluída) e `cancelled` (cancelada com justificativa).
* **Recebimento Físico Integrado com Anexo de NF-e:** Ao conferir a entrega da mercadoria, o número da Nota Fiscal (DANFE) e anexar o arquivo digital comprobatório (PDF/XML/Imagem), o módulo de compras aciona a rotina interna `register_purchase_receipt` que dá entrada automática no saldo de estoque do almoxarifado com rastreabilidade completa.

### F. Assistente de Reposição Ágil (Giro Rápido & Ponto de Pedido)
* **Cálculo de Necessidade em Tempo Real:** Varre o estoque e identifica produtos com saldo abaixo do Estoque Mínimo de Segurança.
* **Classificação de Urgência:**
  * 🔴 **Crítico / Ruptura:** Saldo Zerado.
  * 🟡 **Alto / Ponto de Pedido:** Saldo abaixo do mínimo.
  * 🟢 **Normal / Regular:** Saldo dentro do alvo.
* **Segregação Estrita de Funções (SoD - *Segregation of Duties*):** O comprador **não tem permissão para ajustar saldo físico diretamente em compras**. Toda movimentação de estoque originada em compras ocorre exclusivamente por meio do ciclo formal de Ordem de Compra ou Recebimento de NF. O botão por linha no Assistente de Compras permite a emissão ágil e direta de Ordem de Compra para o item (`⚡ Gerar Pedido Direto`).
* **Emissão Direta em Lote ou Individual:** Permite selecionar múltiplos itens sugeridos ou emitir pedidos rápidos individualizados para o fornecedor.

---

## 3. O que Falta Implementar (Roadmap & Próximas Fases)

De acordo com o backlog oficial ([`docs/05-backlog.md`](file:///c:/Users/jeffe/ControlB/docs/05-backlog.md)):

1. **Alçadas de Aprovação Multi-Nível por Faixa de Valor:**
   - Regras configuráveis de alçada:
     - Até R$ 5.000: Aprovação do Supervisor de Setor.
     - De R$ 5.001 a R$ 50.000: Exige aprovação adicional do Gerente de Compras.
     - Acima de R$ 50.000: Exige aprovação formal da Diretoria Financeira.
2. **Portal Externo de Cotações para Fornecedores:**
   - Envio de e-mail com link exclusivo e seguro (*tokenizado*) para o fornecedor preencher seus próprios preços e prazos diretamente na web, sem necessidade do comprador digitar manualmente.
3. **Leitura e Importação de XML de NF-e (Danfe):**
   - Upload de arquivo `.xml` da Nota Fiscal Eletrônica com cruzamento automatizado (*3-way matching*: Pedido × Nota Fiscal × Entrada Física).
4. **Gestão de Aditivos Contratuais e Histórico de Renegociação em POs:**
   - Versionamento de Ordens de Compra já emitidas caso haja alteração de quantidade ou renegociação de preços.
