# Proposta Arquitetural: Mecanismo Universal de Importação & Mapeador Dinâmico de Planilhas (XLSX / CSV)

> **Status:** 📋 Documentado para Implementação Futura  
> **Módulos Beneficiados:** Estoque / Almoxarifado, Compras, Financeiro e Faturamento.  
> **Objetivo:** Permitir a importação e conciliação de qualquer planilha (.xlsx ou .csv) de sistemas legados desconhecidos através de um assistente de "De-Para" de colunas, templates salvos e conciliação prévia em sandbox (Dry-Run).

---

## 1. O Problema & A Oportunidade

### Cenário Atual:
- O ControlB possui um motor de alta velocidade desenvolvido especificamente para a planilha do **ToolsPharma**, que reconhece colunas fixas e quebras de página nativas do sistema.

### Cenário Futuro (Necessidade de Generalização):
- Diferentes clínicas, hospitais e farmácias utilizam sistemas legados diversos (*Totvs Protheus, Senior, SAP Business One, Linx Farma, Sankhya, Alterdata, etc.*) ou planilhas manuais do Excel.
- Desenvolver um endpoint e parser em código Python para cada sistema torna a manutenção cara e lenta.
- **Solução:** Um **Mapeador Dinâmico de Importação (*Dynamic Schema Mapper*)**, onde o usuário faz o upload de qualquer planilha, o sistema detecta as colunas disponíveis e permite que o operador configure e salve o mapeamento visualmente.

---

## 2. Arquitetura Proposta em 3 Etapas

```
                                FLUXO DO MAPEADOR DINÂMICO
                                
   [ Planilha Qualquer ] ───► 1. INSPEÇÃO & DETECÇÃO DE CABEÇALHOS (Schema Sniffer)
     (.xlsx ou .csv)             • Lê headers e tipos inferidos
                                 • Gera amostra de 5 linhas
                                         │
                                         ▼
                              2. WIZARD VISUAL DE "DE-PARA" (Column Mapping)
                                 • Campo ControlB ◄──► Coluna da Planilha
                                 • Regras de transformação e fallback
                                 • Opção: "Salvar como Modelo de Importação"
                                         │
                                         ▼
                              3. STAGING & CONCILIAÇÃO PRÉVIA (Dry-Run Sandbox)
                                 • Pré-visualização de impactos (Novos, Vendas, Entradas)
                                 • Destaque visual de erros de validação
                                 • Edição manual na grade antes de confirmar
                                         │
                                         ▼
                              4. EXECUÇÃO TRANSACIONAL & AUDITORIA KARDEX
```

---

## 3. Especificação Técnica dos Componentes

### A. Modelo de Dados para Armazenamento de Templates (`ImportTemplate`)

Para que o usuário não precise refazer o mapeamento a cada importação diária, o sistema guardará a configuração na tabela `import_template`:

```python
class ImportTemplate(Base):
    __tablename__ = "import_template"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    
    name: Mapped[str] = mapped_column(String(200))  # Ex: "Relatório Diário - Linx Farma"
    target_entity: Mapped[str] = mapped_column(String(50))  # "inventory_product", "financial_payable", etc.
    file_type: Mapped[str] = mapped_column(String(10))  # "xlsx" ou "csv"
    has_header: Mapped[bool] = mapped_column(Boolean, default=True)
    header_row_index: Mapped[int] = mapped_column(Integer, default=1)
    
    # Mapeamento JSON serializado
    # Ex: {"sku": "Col A", "name": "Descrição", "current_stock": "Saldo Físico", "cost_price": "Custo Unit"}
    field_mappings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Regras de conciliação (ex: "detect_deltas": True, "create_missing_categories": True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

---

### B. Endpoints REST da API (Futura)

1. **`POST /import/inspect-headers`**
   - **Entrada:** Arquivo `.xlsx` ou `.csv`
   - **Saída:** Lista de colunas identificadas, linha inicial estimada e amostra das primeiras 5 linhas.
2. **`POST /import/preview-dry-run`**
   - **Entrada:** Arquivo + `field_mappings` + `options`
   - **Saída:** Relatório simulado de impacto:
     - Linhas válidas vs linhas com erro de tipagem;
     - Total de novos cadastros;
     - Total de vendas / saídas estimadas;
     - Total de entradas / reposições estimadas;
     - Grade de dados pré-processados prontos para conferência.
3. **`POST /import/execute`**
   - **Entrada:** Token da sessão de staging validada ou arquivo + templateId
   - **Saída:** Confirmação da transação com métricas consolidadas.
4. **`GET / POST / PUT / DELETE /import/templates`**
   - Gerenciamento de modelos salvos pela organização.

---

### C. Interface do Usuário (Frontend UX)

1. **Passo 1: Upload & Escolha de Modelo**
   - Seleção do arquivo + Dropdown: *"Usar Modelo Salvo"* ou *"Configurar Novo Mapeamento"*.
2. **Passo 2: Construtor Visual de De-Para (Mapping Builder)**
   - Tabela com duas colunas:
     - Esquerda: Campos do ControlB (*Código/SKU*, *Nome*, *NCM*, *Saldo*, *Custo*, *Venda*, *Unidade*, *Categoria*).
     - Direita: Dropdowns populados dinamicamente com as colunas detectadas no arquivo (ex: `Col A - Cód`, `Col E - EAN`, `Col I - Produto`).
   - Checkbox: *"Salvar este mapeamento para importações futuras"*.
3. **Passo 3: Grade Interativa de Pré-Conciliação (Sandbox Grid)**
   - Exibição de linhas em verde (novos), azul (entradas), vermelho (vendas) e amarelo (divergências de digitação).
   - Possibilidade de corrigir um NCM ou preço diretamente na célula antes de confirmar.

---

## 4. Benefícios Estratégicos & Vantagens

1. **Independência de Software de Origem:** O cliente pode migrar ou integrar com qualquer ERP farmacêutico/hospitalar sem depender de alterações no código-fonte.
2. **Segurança contra Ingestão de Dados Corrompidos:** A etapa de pré-visualização (Dry-Run) impede que arquivos mal formatados ou com colunas trocadas quebrem o saldo real do almoxarifado.
3. **Reutilização Operacional:** Modelos criados por usuários administradores ficam disponíveis para qualquer operador de almoxarifado com apenas 1 clique diário.
