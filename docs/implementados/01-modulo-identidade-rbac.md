# Livro de Implementação do ControlB — Capítulo 1: Módulo de Identidade, Autenticação e RBAC

---

## 1. Contexto & Propósito do Módulo

O módulo **Identity** é a base de segurança e controle de acesso de todo o ecossistema ControlB. Ele garante que:
1. **Multi-tenancy Rígido:** Cada organização/empresa opera de maneira 100% isolada. Usuários só enxergam dados pertencentes ao seu próprio `organization_id`.
2. **Autenticação Segura:** Sessões gerenciadas por JSON Web Tokens (JWT) com criptografia assimétrica e hash de senha via `bcrypt`.
3. **Controle de Acesso Baseado em Funções (RBAC Granular):** Nenhuma ação crítica no sistema pode ser executada sem a verificação explícita de permissões (ex: `purchasing:approve`, `inventory:adjust`, `users:manage`).

---

## 2. O que foi Implementado (100% Entregue)

### A. Modelagem do Banco de Dados ([`modules/identity/models.py`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/identity/models.py))

* **`organization`:** Entidade multi-tenant raiz (ID, Nome Oficial, CNPJ/Documento, Status Ativo, Datas de Criação e Atualização).
* **`user_account`:** Usuários do sistema (ID, Nome Completo, E-mail Único, Hash da Senha Bcrypt, `organization_id`, `role_id`, Status Ativo).
* **`role`:** Cargos e perfis de função (ex: *Administrador Geral*, *Comprador Pleno*, *Almoxarife*, *Gestor Financeiro*, *Diretor Aprovador*).
* **`permission`:** Catálogo de permissões atômicas do sistema (ex: `dashboard:view`, `purchasing:create`, `purchasing:approve`, `inventory:view`, `inventory:adjust`, `users:view`, `users:manage`).
* **`role_permission`:** Tabela associativa N:N ligando permissões aos cargos.

### B. Serviços & Regras de Negócio ([`modules/identity/service.py`](file:///c:/Users/jeffe/ControlB/_controlB/src/controlb/modules/identity/service.py))

* **Autenticação OAuth2:** Endpoint `/identity/token` que valida credenciais, verifica status ativo do usuário e emite o Bearer Token JWT contendo `sub` (User ID), `org_id` (Organization ID) e `exp` (Data de Expiração).
* **Injeção de Dependência de Segurança (`get_current_user`):** Interceptador FastAPI que decodifica o JWT, valida a assinatura e recupera a instância ativa do usuário diretamente no banco.
* **Verificador de Permissão (`has_permission`):** Função que inspeciona dinamicamente a lista de permissões associada ao cargo do usuário logado.
* **CRUD de Usuários, Cargos e Organizações:** Endpoints restritos para criação, listagem, edição de perfil, ativação/desativação e reatribuição de cargos.

### C. Frontend & Proteção de Interface ([`frontend/src/`](file:///c:/Users/jeffe/ControlB/_controlB/frontend/src/))

* **`usePermissions` Hook:** Hook personalizado que carrega os dados do usuário autenticado via `/identity/me` e disponibiliza métodos reativos: `hasPermission('permissao')` e `hasAnyPermission(['perm1', 'perm2'])`.
* **`<Can />` Component:** Wrapper declarativo para renderização condicional de botões e ações no JSX:
  ```tsx
  <Can do="purchasing:approve">
    <button className="btn-approve">Aprovar Solicitação</button>
  </Can>
  ```
* **Rotas Públicas e Protegidas (`ProtectedRoute` & `PublicRoute`):** Redirecionamento automático para `/login` caso o token JWT não exista no `localStorage`, e para `/dashboard` caso o usuário já esteja autenticado.
* **Página de Cadastros Administrativos (`Cadastros.tsx`):** Gestão integrada de Organizações, Usuários e Matriz de Permissões de Cargos com interface moderna e responsiva.

---

## 3. O que Falta Implementar (Roadmap & Próximas Fases)

De acordo com as diretrizes de segurança avançada do documento de arquitetura ([`docs/07-qualidade-seguranca.md`](file:///c:/Users/jeffe/ControlB/docs/07-qualidade-seguranca.md)):

1. **Autenticação de Dois Fatores (2FA / MFA via TOTP):**
   - Suporte a Google Authenticator / Microsoft Authenticator com geração de segredo Base32 e verificação de código de 6 dígitos no login.
2. **Recuperação de Senha por E-mail:**
   - Fluxo de "Esqueci minha senha" com geração de token de uso único (*Magic Link* com validade de 15 minutos) e envio seguro via serviço de e-mail (SMTP/SES).
3. **Trilha de Auditoria Específica de Autenticação (*Auth Logs*):**
   - Registro de tentativas falhas de login, bloqueio temporário de IP após 5 tentativas consecutivas (*Rate Limiting*) e histórico de sessões ativas com revogação forçada.
4. **Troca de Senha Obrigatória no Primeiro Acesso:**
   - Flag `must_change_password: bool` forçando o usuário a definir uma nova senha segura no primeiro login.
