/**
 * login.js - Lógica de autenticação e comunicação com a API FastAPI
 * 
 * Responsabilidades:
 * 1. Interceptar o evento de envio do formulário de login (sem recarregar a tela).
 * 2. Obter os dados digitados (e-mail e senha).
 * 3. Enviar a requisição no padrão OAuth2 Form-Data para a rota '/identity/token'.
 * 4. Salvar o token JWT retornado no localStorage do navegador.
 * 5. Redirecionar para o dashboard (/dashboard) ou exibir feedback visual de erro.
 */

// Garante que o código só execute após todo o DOM da página HTML estar completamente carregado
document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Mapeamento dos elementos da interface pelo ID
    const loginForm = document.getElementById('loginForm');       // Formulário HTML
    const emailInput = document.getElementById('email');           // Campo de texto do E-mail
    const passwordInput = document.getElementById('password');     // Campo de texto da Senha
    const submitBtn = document.getElementById('submitBtn');       // Botão "Entrar"
    const errorMsg = document.getElementById('errorMsg');         // Mensagem vermelha de erro
    const glassPanel = document.querySelector('.glass-panel');    // Painel visual de vidro (para animação shake)

    // Se o formulário não existir na página, encerra a execução
    if (!loginForm) return;

    // 2. Escuta o evento 'submit' disparado quando o usuário clica em "Entrar" ou aperta Enter
    loginForm.addEventListener('submit', async (event) => {
        
        // Impede o comportamento padrão do navegador (que seria recarregar toda a página)
        event.preventDefault();

        // Obtém e sanitiza os valores digitados pelo usuário
        const email = emailInput.value.trim(); // .trim() remove espaços em branco acidentais antes e depois
        const password = passwordInput.value;

        // 3. Feedback Visual de "Carregando":
        // Altera o texto do botão e desativa a mensagem de erro antiga para melhorar a experiência do usuário
        submitBtn.innerHTML = 'Autenticando...';
        submitBtn.style.opacity = '0.8';
        errorMsg.classList.remove('visible');

        try {
            // 4. Preparação dos dados para o FastAPI:
            // O padrão OAuth2PasswordRequestForm espera dados no formato 'application/x-www-form-urlencoded'.
            // Por especificação do protocolo OAuth2, o e-mail é passado no campo com a chave 'username'.
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);

            // 5. Chamada de API HTTP POST:
            // Usamos o caminho relativo '/identity/token' que passa pelo proxy reverso Nginx na porta 80
            const response = await fetch('/identity/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData
            });

            // 6. Tratamento de Sucesso (HTTP 200 OK):
            if (response.ok) {
                // Converte a resposta JSON retornada pelo backend: {"access_token": "...", "token_type": "bearer"}
                const data = await response.json();

                // Feedback visual de sucesso: muda botão para verde
                submitBtn.innerHTML = 'Sucesso! Entrando...';
                submitBtn.style.background = '#10b981';

                // Armazena o token JWT no armazenamento local (localStorage) do navegador.
                // Isso permite que o usuário permaneça logado e acesse o Dashboard sem precisar digitar senha novamente.
                localStorage.setItem('controlb_token', data.access_token);

                // Redireciona o usuário para a rota limpa do dashboard (/dashboard) após 400 milissegundos
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 400);

            } else {
                // Se a API retornou código de erro (como HTTP 401 Credenciais Inválidas), lança uma exceção
                throw new Error('Falha na autenticação');
            }

        } catch (err) {
            // 7. Tratamento de Erro (Senha incorreta ou falha de conexão):

            // Restaura o botão para o estado original
            submitBtn.innerHTML = 'Entrar';
            submitBtn.style.opacity = '1';
            submitBtn.style.background = '';

            // Torna visível a mensagem vermelha de erro ("Credenciais inválidas")
            errorMsg.classList.add('visible');

            // Efeito visual de "Tremida" (Shake) no painel de vidro para indicar erro ao usuário
            if (glassPanel) {
                glassPanel.style.transition = 'transform 0.1s';
                glassPanel.style.transform = 'translateX(10px)';                       // Move 10px pra direita
                setTimeout(() => glassPanel.style.transform = 'translateX(-10px)', 100); // Move 10px pra esquerda
                setTimeout(() => glassPanel.style.transform = 'translateX(10px)', 200);  // Move de novo pra direita
                setTimeout(() => glassPanel.style.transform = 'translateX(0)', 300);     // Volta para o centro
                setTimeout(() => glassPanel.style.transition = '', 400);                 // Reseta a transição
            }
        }
    });
});
