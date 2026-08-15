/**
 * dashboard.js - Lógica da página inicial (Dashboard) do ControlB
 * 
 * Responsabilidades:
 * 1. Proteção de Rota: Validar se o token JWT existe no localStorage (se não, chuta pro /login).
 * 2. Realizar chamadas autenticadas via header 'Authorization: Bearer <token>' para a API FastAPI.
 * 3. Buscar e renderizar listas de Usuários, Cargos (Roles) e Organizações nos cards do Grid.
 * 4. Gerenciar a ação de Logout e expiração de sessão.
 */

// Prefixo base da API: Vazio pois o Nginx na porta 80 já faz o roteamento transparente de '/identity/...'
const API_BASE_URL = '';

// 1. PRIMEIRA BARREIRA DE PROTEÇÃO:
// Busca o token salvo na memória do navegador pelo login.js
const token = localStorage.getItem('controlb_token');

// Se não houver token (usuário tentou acessar direto pela URL sem logar), redireciona imediatamente para o /login
if (!token) {
    window.location.href = '/login';
}

/**
 * 2. FUNÇÃO DE LOGOUT
 * É executada quando o usuário clica no botão "Sair" da Navbar ou quando uma requisição retorna 401 (token expirado).
 */
function fazerLogout() {
    // Remove o token do navegador para invalidar a sessão local
    localStorage.removeItem('controlb_token');

    // Redireciona o usuário para a página de login
    window.location.href = '/login';
}

/**
 * 3. FUNÇÃO: Buscar e Listar Usuários
 * Faz um GET em '/identity/users' passando o JWT no cabeçalho.
 */
async function carregarUsuarios() {
    const ul = document.getElementById('lista-usuarios');
    try {
        const response = await fetch(`${API_BASE_URL}/identity/users`, {
            method: 'GET',
            headers: {
                // ** O SEGREDO DA AUTENTICAÇÃO **: O token JWT é enviado como Bearer Token no header Authorization
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        // Se o status for 200 OK
        if (response.ok) {
            const usuarios = await response.json();
            ul.innerHTML = ''; // Limpa a mensagem inicial "Carregando..."

            // Caso o banco não tenha nenhum usuário cadastrado
            if (usuarios.length === 0) {
                ul.innerHTML = '<li>Nenhum usuário cadastrado.</li>';
                return;
            }

            // Itera sobre a lista de usuários e cria um <li> para cada um
            usuarios.forEach(user => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>${user.full_name}</strong><br><small>${user.email}</small>`;
                ul.appendChild(li);
            });

        } else {
            // Se retornar erro 401 (token expirou ou foi invalidado), avisa e faz logout
            alert('Sessão expirada. Faça login novamente.');
            fazerLogout();
        }

    } catch (err) {
        console.error('Erro ao buscar usuários:', err);
        if (ul) ul.innerHTML = '<li>Erro ao carregar os dados. A API está ligada?</li>';
    }
}

/**
 * 4. FUNÇÃO: Buscar e Listar Cargos/Funções (Roles)
 * Faz um GET em '/identity/role' passando o JWT no cabeçalho.
 */
async function carregarRoles() {
    const ul = document.getElementById('lista-roles');
    try {
        const response = await fetch(`${API_BASE_URL}/identity/role`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const roles = await response.json();
            ul.innerHTML = ''; // Limpa a mensagem "Carregando..."

            if (roles.length === 0) {
                ul.innerHTML = '<li>Nenhum cargo cadastrado.</li>';
                return;
            }

            // Itera sobre os cargos e renderiza o nome e descrição
            roles.forEach(role => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>${role.name}</strong><br><small>${role.description || 'Sem descrição'}</small>`;
                ul.appendChild(li);
            });

        } else {
            alert('Sessão expirada. Faça login novamente.');
            fazerLogout();
        }

    } catch (err) {
        console.error('Erro ao buscar roles:', err);
        if (ul) ul.innerHTML = '<li>Erro ao carregar os dados.</li>';
    }
}

/**
 * 5. FUNÇÃO: Buscar e Listar Organizações (Empresas/Unidades)
 * Faz um GET em '/identity/organization' passando o JWT no cabeçalho.
 */
async function carregarOrganizacoes() {
    const ul = document.getElementById('lista-organizacoes');
    try {
        const response = await fetch(`${API_BASE_URL}/identity/organization`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const organizacoes = await response.json();
            ul.innerHTML = ''; // Limpa a mensagem "Carregando..."

            if (organizacoes.length === 0) {
                ul.innerHTML = '<li>Nenhuma organização cadastrada.</li>';
                return;
            }

            // Itera sobre as organizações e formata o status de ativação
            organizacoes.forEach(org => {
                const li = document.createElement('li');
                const statusTexto = org.is_active ? 'Ativa' : 'Inativa';
                li.innerHTML = `<strong>${org.name}</strong><br><small>Status: ${statusTexto}</small>`;
                ul.appendChild(li);
            });

        } else {
            alert('Sessão expirada. Faça login novamente.');
            fazerLogout();
        }

    } catch (err) {
        console.error('Erro ao buscar organizações:', err);
        if (ul) ul.innerHTML = '<li>Erro ao carregar os dados.</li>';
    }
}

/**
 * 6. GATILHO INICIAL:
 * Assim que o HTML termina de ser construído no navegador, dispara as 3 requisições em paralelo.
 */
document.addEventListener('DOMContentLoaded', () => {
    carregarUsuarios();
    carregarRoles();
    carregarOrganizacoes();
});
