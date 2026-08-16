# Livro de Implementação do ControlB — Capítulo 6: Arquitetura Frontend SPA, Nginx e DevOps

---

## 1. Contexto & Padrões de Engenharia

Para entregar uma experiência de uso rápida, responsiva e com nível corporativo, o ControlB combina **tecnologias modernas de frontend SPA**, **proxy reverso unificado** e **automação local robusta de desenvolvimento e testes**.

---

## 2. O que foi Implementado (100% Entregue)

### A. Frontend SPA com Layout Persistente ([`frontend/src/`](file:///c:/Users/jeffe/ControlB/_controlB/frontend/src/))

1. **Stack Tecnológica:**
   - React 18, TypeScript 5, Vite 8 e Design System próprio em Vanilla SCSS com variáveis semânticas CSS (Tokens para Dark e Light mode).
2. **Arquitetura de Layout Persistente (`AppLayout`):**
   - A barra de navegação superior (`Navbar`) é montada uma única vez no topo do `AppLayout`.
   - Ao transitar entre módulos (`/dashboard`, `/estoque`, `/compras`, `/cadastros`), **o cabeçalho nunca é recarregado ou destruído**, eliminando qualquer tipo de piscar ou lentidão visual.
3. **Design System & Componentes Reutilizáveis:**
   - **`Modal.tsx` & `Modal.scss`:** Diálogos acessíveis e responsivos com tamanhos padronizados (`sm`, `md`, `lg: 860px`, `xl: 1080px`).
   - **`ConfirmModal.tsx`:** Diálogo de confirmação de exclusão e cancelamento estilizado, eliminando os `window.confirm` nativos e feios do navegador.
   - **`Can.tsx`:** Componente de autorização granular no JSX via RBAC.
   - **`ThemeContext.tsx`:** Alternador instantâneo de tema Claro/Escuro com persistência no `localStorage`.
4. **Sanitizador Universal de Erros (`formatApiError`):**
   - Blindagem total do React contra erros de validação HTTP 422 do FastAPI/Pydantic.
   - Converte arrays complexos de erros (`[{type, loc, msg}]`) em mensagens amigáveis em português, prevenindo qualquer crash de renderização no JSX.

---

### B. Gateway & Proxy Reverso com Nginx ([`nginx/nginx.conf`](file:///c:/Users/jeffe/ControlB/nginx/nginx.conf))

1. **Porta Única de Entrada (Porta 80):**
   - O desenvolvedor e o usuário final acessam tudo através de `http://localhost/` sem precisar gerenciar portas separadas ou lidar com bloqueios de CORS.
2. **Roteamento Inteligente:**
   - `location /`: Encaminha para o servidor de desenvolvimento Vite (porta `9090`).
   - `location ^~ /identity/`: Encaminha chamadas de autenticação e RBAC para o FastAPI (porta `8000`).
   - `location ^~ /purchasing/`: Encaminha requisições do módulo de Compras para o FastAPI (porta `8000`).
   - `location ^~ /inventory/`: Encaminha requisições do Almoxarifado para o FastAPI (porta `8000`).
   - `location ^~ /financial/`: (Planejado) Encaminhará requisições de Gestão Financeira.
   - `location ^~ /billing/`: (Planejado) Encaminhará requisições de Faturamento e Vendas.

---

### C. Suite de Testes Automatizados no Backend ([`tests/unit/`](file:///c:/Users/jeffe/ControlB/_controlB/tests/unit/))

1. **26 Testes Unitários com 100% de Sucesso (`pytest`):**
   - `test_inventory_service.py`: Movimentações por NF, baixas por avaria, balanço e recebimento de PO.
   - `test_purchasing_categories_and_suppliers.py`: CRUD e integridade de fornecedores e categorias.
   - `test_purchasing_po_flow.py`: Emissão de PO, cálculo de frete/desconto e recebimento no almoxarifado.
   - `test_purchasing_quotation_flow.py`: Abertura de RFQ, cotações concorrentes e mapa comparativo.
   - `test_purchasing_replenishment.py`: Algoritmo de giro rápido e ponto de pedido.
   - `test_purchasing_request_deletion.py`: Desvinculação segura e exclusão de solicitações.
   - `test_purchasing_sku.py`: Gerador determinístico e sequencial de SKU.

---

### D. Automação de Ambiente Local via PowerShell

1. **`control_start.ps1`:** Sobe o banco de dados PostgreSQL no Docker, executa as migrações do Alembic, inicializa a API FastAPI em background e inicializa o servidor Vite com o proxy Nginx.
2. **`control_stop.ps1`:** Encerra com segurança todos os processos ativos e serviços em execução.
3. **`control_restart.ps1`:** Realiza o reinício coordenado e limpo de todos os componentes da stack.

---

## 3. O que Falta Implementar (DevOps & Qualidade)

1. **Pipeline de CI/CD (GitHub Actions / GitLab CI):**
   - Execução automática de `pytest`, `ruff`/`flake8`, `mypy` e `npm run build` a cada Pull Request.
2. **Testes End-to-End (E2E) no Frontend:**
   - Suite de testes automatizados com Playwright cobrindo o fluxo completo do usuário (Login -> Emitir SC -> Aprovar -> Cotar -> Emitir PO -> Receber no Almoxarifado -> Gerar Título Financeiro).
3. **Observabilidade & Monitoramento em Produção:**
   - Integração com Sentry para captura de exceções em tempo real e Prometheus/Grafana para métricas de latência e consumo de banco.
