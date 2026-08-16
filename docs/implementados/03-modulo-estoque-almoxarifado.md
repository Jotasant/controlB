# Livro de Implementação do ControlB — Capítulo 3: Módulo de Estoque e Almoxarifado

---

## 1. Contexto & Propósito do Módulo

O módulo **Inventory (Estoque & Almoxarifado)** é responsável pela guarda física, rastreabilidade sanitária, controle de giro e governança contábil dos insumos, medicamentos e materiais da instituição.

Diferente de sistemas amadores onde o saldo é apenas um número solto no banco, no ControlB **o estoque é gerido pelo princípio de Livro-Razão Imutável (*Stock Ledger / Kardex*)**. Cada variação de saldo é fruto de uma transação auditada, carimbada no tempo com o usuário responsável e documento comprobatório.

---

## 2. O que foi Implementado (100% Entregue)

### A. Roteamento Dedicado & Arquitetura de Módulo ([`frontend/src/pages/Inventory/`](file:///c:/Users/jeffe/ControlB/_controlB/frontend/src/pages/Inventory/))
* **Módulo Individualizado:** Rota protegida `/estoque` com navegação pelo Navbar superior, segregando totalmente a operação do almoxarife das negociações comerciais do comprador.
* **Layout Estruturado & Responsivo:** Sidebar lateral temática, barra de busca instantânea, filtros por status de estoque (Críticos, Zerados, Regulares) e categorias de produtos.

### B. Catálogo Avançado de Produtos & Insumos ([`Product`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/inventory/models.py))
* **Gerador Inteligente de SKU (`generate_product_sku`):** Criação padronizada de códigos únicos (ex: `MED-DIP-FR-0001`) baseada na categoria, nome e unidade.
* **Parâmetros de Ressuprimento:**
  * **Estoque Mínimo (Ponto de Pedido):** Gatilho que aciona o Assistente de Compras.
  * **Estoque Alvo (Máximo Desejado):** Quantidade ideal de reposição para evitar excesso e custos de armazenagem.
  * **Endereçamento no Almoxarifado:** Corredor, estante, prateleira ou gaveta (ex: *Corredor B - Prateleira 3*).
* **Rastreabilidade Sanitária & Fiscal:**
  * Código de Barras Global (EAN-13 / GTIN).
  * Classificação Fiscal (NCM).
  * Marca / Fabricante / Laboratório.
  * Checkbox de Item Perecível e Prazo de Validade Padrão (*Shelf Life* em dias).
  * Exigência obrigatória de Lote e Validade nas entradas.

### C. Imutabilidade do Saldo Cadastral
* O campo `current_stock` no formulário de edição de produtos foi transformado em **Card Informativo Somente-Leitura (Read-Only)**.
* Ninguém pode digitar números aleatórios para "acertar" o estoque sem passar pela esteira formal de movimentação auditada.

### D. Wizard de Movimentação & Auditoria de Estoque
Criado um diálogo moderno com **3 abas dinâmicas especializadas**:

```
                         WIZARD DE MOVIMENTAÇÃO DE ESTOQUE
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
 1. ENTRADA POR NOTA           2. BAIXA JUSTIFICADA           3. CONCILIAÇÃO FÍSICA
    • Número da NF-e *            • Motivo Padronizado *         • Saldo Sistema (ex: 8)
    • Fornecedor / Razão          • Qtd a Baixar (-) *           • Saldo Contado (ex: 10)
    • Qtd Recebida (+) *          • Justificativa Formal *       • Divergência (+2 Sobra)
    • Custo Unitário (R$)                                        • Auditor Responsável *
    • Lote e Validade                                            • Parecer da Auditoria *
```

1. **📄 Aba 1: Entrada por Nota Fiscal (`in_invoice`):**
   - Registro de compra direta ou remessa complementar exigindo o número da NF-e, Razão Social do fornecedor, quantidade recebida (+), custo unitário, número do lote e data de validade.
2. **📉 Aba 2: Baixa Técnica Justificada (`out_loss`):**
   - Baixas com validação de saldo máximo (não permite baixar mais do que existe).
   - Motivos padronizados: *Avaria / Quebra de Frasco*, *Validade Expirada*, *Consumo Interno / Amostra*, *Descarte Técnico Regulatório* ou *Extravio*.
   - Exigência de justificativa detalhada obrigatória.
3. **⚖️ Aba 3: Conciliação de Inventário Físico (`reconciliation`):**
   - **Painel de Divergência em Tempo Real:** Exibe o saldo do sistema vs o saldo contado pelo almoxarife e calcula instantaneamente:
     - `+X UN (Sobra de Estoque)` em verde.
     - `-X UN (Quebra / Falta de Estoque)` em vermelho.
     - `0 UN (Saldo Físico Conciliado)` em neutro.
   - Grava formalmente o **Nome do Auditor** e o **Parecer da Auditoria**.

### E. Painel Dedicado de Auditoria & Inventário Físico
* **View Especializada (`/estoque` -> Auditoria & Inventário):**
  * **Métricas de Governança:**
    * Taxa de Acuracidade Global do Inventário (%).
    * Total de Itens Auditados vs Pendentes de Contagem.
    * Total de Divergências Físicas Apuradas (Sobras, Quebras e Avarias).
    * Patrimônio Total Avaliado em Estoque (R$).
  * **Painel de Balanço e Aferição por SKU:** Tabela com todos os produtos, localização física, saldo no sistema, status de auditoria e botão de ação direta **"Auditar Saldo"** (aciona o wizard de conciliação).
  * **Extrato Histórico de Pareceres e Divergências:** Histórico formal e imutável de todas as contagens, baixas técnicas e correções de inventário contendo parecer, auditor e documento.

### F. Anexo e Armazenamento de Arquivos de Notas Fiscais (PDF / XML / Imagens)
* Suporte nativo ao campo `invoice_attachment` nos modelos de dados de Estoque e Compras.
* Upload integrado no Wizard de Movimentação de Estoque (Aba 1: Entrada por NF) e no Modal de Recebimento de Ordem de Compra.
* Exibição de links e botões de download/visualização direta no Kardex e nos espelhos das Ordens de Compra.
* Estrutura preparada para integração com OCR / Leitor Inteligente de XML da SEFAZ.

### G. Extrato Cronológico de Movimentações (*Kardex*)
* Tabela completa exibindo data/hora, produto, tipo de movimento com badges coloridos (`Entrada por NF`, `Entrada por Compra`, `Sobra de Inventário (+)`, `Falta de Inventário (-)`, `Baixa por Perda/Avaria`), quantidade, custo unitário, documento de referência com anexo de NF e saldo final após a movimentação.

---

## 3. O que Falta Implementar (Roadmap & Próximas Fases)

De acordo com o roadmap de estoque ([`docs/04-roadmap.md`](file:///c:/Users/jeffe/ControlB/docs/04-roadmap.md) e [`docs/05-backlog.md`](file:///c:/Users/jeffe/ControlB/docs/05-backlog.md)):

1. **Recebimento Parcial Fracionado de Ordens de Compra:**
   - Permitir que uma Ordem de Compra de 100 frascos seja recebida em 2 entregas (ex: 60 frascos na NF 101 e 40 frascos na NF 108), mantendo o status `partially_received` até a liquidação final.
2. **Inventário Físico com Contagem Cega (*Blind Count*):**
   - Emissão de folhas de contagem onde o almoxarife não enxerga o saldo cadastrado no sistema antes de digitar a contagem real, prevenindo vícios de conferência.
3. **Leitura de Código de Barras / QR Code via Câmera ou Coletor:**
   - Integração com coletores de dados e câmeras de dispositivos móveis para conferência ágil de SKU, EAN e lote.
4. **Gestão Multi-Almoxarifado & Transferência entre Depósitos:**
   - Criação de múltiplos depósitos (ex: *Almoxarifado Central*, *Farmácia Satélite UTI*, *Depósito Centro Cirúrgico*) com solicitações e transferências internas de estoque.
