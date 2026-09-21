# Chat — gateway e API

## Etapa disponível

Backend de conexões, conversas vinculadas a documentos, mensagens de texto e
webhooks. O primeiro adaptador é Evolution API; os serviços usam o contrato
`ChatConnector` e o registro de fábricas, sem importar o adaptador diretamente.
A interface possui Chat → Conexões, com formulário de registro nas abas
Configuração, Equipe e Conexão. A aba Equipe lista apenas os participantes e oferece
busca e inclusão pelo botão Adicionar participante, sempre dentro da organização.
As conversas ficam no widget persistente, sem uma página
isolada de conversa. O acesso administrativo exige `chat:manage_connectors`.

## Iniciar atendimento, origem e nomes

No widget, o botão **+ / Nova conversa** permite escolher um contato ativo da
organização e uma instância da qual o usuário participa. Para novo cadastro, use
o link **Cadastrar um novo contato** (formulário completo) e **Salvar e conversar**.
Um contato existente oferece **Conversar no WhatsApp** no rodapé do formulário.
`POST /chat/conversations/start` recebe `connection_id` e `contact_id`, exige
`chat:send` e não exige proposta/projeto. O telefone é validado com DDI/DDD e
deduplicado no contexto da organização. Um canal existente é reutilizado, sem
reabrir/desarquivar nem enviar mensagem automaticamente.

**Canal de aquisição** identifica Instagram, Google, Lead, indicação, campanha
etc. É a origem comercial do contato, não seu meio de comunicação. O cadastro
gerado por WhatsApp continua identificado por `origin_module=CHAT`, mas novos
contatos não recebem automaticamente uma origem comercial “WhatsApp”. Origens
anteriores são preservadas e podem ser alteradas pelo seletor. As sugestões do
seletor são criadas/reutilizadas ao escolher; novas opções continuam disponíveis.

Recebimento usa o nome de perfil informado no payload WhatsApp. Eventos
`CONTACTS_UPDATE` e `CONTACTS_UPSERT` também atualizam nomes da agenda sincronizada.
Reconfigure o webhook de instâncias anteriores para incluir esses eventos.
Somente mensagens recebidas fornecem `pushName`; o nome do atendente não nomeia
o contato. Se nenhum nome estiver disponível, permanece o número. Nomes
preenchidos manualmente no Identity são preservados.

O envio e o webhook não aguardam consultas remotas de nomes. A sincronização de
histórico e a ação **⋯ → Atualizar nome WhatsApp** consultam `findContacts` na
própria instância, por telefone exato, com timeout de três segundos e concorrência
limitada. Uma agenda vazia não descarta o nome presente na mensagem recebida.
Essas consultas ocorrem antes do bloqueio transacional da conexão, com revalidação
do acesso e da instância após a resposta. A ação usa
`POST /chat/conversations/{id}/refresh-contact` e exige `chat:send` e acesso ao canal.
O ControlB depende dos nomes que a Evolution disponibiliza nos eventos/agenda.

No widget, ações e origem ficam recolhidas em **⋯ / Ações e dados da conversa**.
O componente é renderizado fora dos formulários dos módulos. O envio mantém a
chave idempotente em falhas incertas, mostra status/erros e mantém o texto para
revisão. A geração de UUID usa `getRandomValues` quando `randomUUID` não existe
(acesso HTTP na rede local). HTTPS continua recomendado para proteção da sessão.

### Aceite, autoria interna e segurança contra reenvio

Resposta de envio bem-sucedida contendo ID externo confirma **SENT / Enviada**,
mesmo quando o corpo da Evolution ainda indica `PENDING`. Isso não significa
entrega ao aparelho: **DELIVERED** e **READ** dependem dos recibos do provedor.
Timeout/5xx sem confirmação continuam incertos, sem tentativa automática adicional.
Recibos repetidos, ecos e reimportações reconciliam o mesmo ID externo e somente
avançam o estado; a sincronização nunca chama `sendText`.

Cada envio do ControlB grava `created_by_id`. A API também retorna `author_name`,
resolvido no usuário da mesma organização, e o widget mostra seu nome de perfil
na bolha. Esse dado é interno e nunca é anexado ao texto enviado ao destinatário.
Envios pelo celular/provedor não têm atendente presumido e aparecem como envio
externo. Sincronização e ecos preservam a autoria de envios locais.

Para reparar registros antigos, `scripts/reconcile_chat_metadata.py` aceita um
`--connection-id UUID` explícito e faz dry-run por padrão; `--apply` confirma.
Apenas saídas pendentes com ID externo, intenção local, autor e sem erro passam
a Enviada. Nomes são recuperados das mensagens recebidas já armazenadas,
preservando nomes manuais. Não há consulta remota, exclusão nem reenvio.

## Configuração do ambiente

Antes de cadastrar uma conexão, configure no servidor:

```dotenv
CHAT_ALLOWED_BASE_URLS=["https://evolution.example"]
CHAT_PUBLIC_BASE_URL=https://controlb.example/api
```

Use a URL real do backend. O prefixo `/api` só é necessário quando o proxy o
expõe. Reinicie o backend após alterar as variáveis. A lista de destinos é
obrigatória e compara URLs exatas, desconsiderando a barra final. Redirecionamentos
HTTP não são seguidos. Use HTTPS em produção e controle a saída de rede no servidor.

Defina também `CHAT_CREDENTIALS_KEY` com um segredo aleatório forte, guardado fora
do repositório. Sem ele, a aplicação deriva a chave de `SECRET_KEY`. A troca da
chave sem recriptografia torna as credenciais armazenadas ilegíveis: mantenha
backup seguro da chave e do banco. Defina a chave dedicada antes de cadastrar
conexões; não reutilize a chave da Evolution.

A instância pode ser criada e pareada pelo ControlB: salve a conexão, abra a aba
Conexão, clique em Criar instância e em Conectar WhatsApp para obter o QR Code.
Leia o código pelo celular; o formulário consulta o status durante o pareamento.
Caso o código expire, solicite outro pelo mesmo botão. Após conectar, clique em
Configurar webhook. Essa ação substitui a configuração de webhook da instância;
prefira uma instância dedicada ao ControlB. Nenhuma mensagem de teste é enviada
automaticamente.

No ambiente local configurado neste projeto, o servidor Evolution é
`http://localhost:8080` e o callback usa `http://host.docker.internal`, passando
pelo Nginx. As rotas de formulário `/chat/conexoes` são encaminhadas ao frontend;
as demais rotas `/chat/` continuam sendo da API.

## Permissões e vínculos

- `chat:view`: canais disponíveis, conversas e histórico.
- `chat:send`: iniciar conversa com contato, envio, atendimento (abrir/fechar/arquivar/assumir) e origem do contato,
  combinado com acesso à conversa.
- `chat:link`: criação de conversas com documentos e alteração de seus vínculos.
- `chat:manage_connectors`: cadastro, credenciais, teste e configuração de webhook.

O usuário precisa pertencer à organização **e ao grupo próprio da instância**,
inclusive se for administrador. Também precisa visualizar todos os documentos
vinculados à conversa: uma conversa associada a proposta e projeto exige acesso
aos dois. Conversas sem documento podem ser atendidas pela equipe, sem exigir
proposta ou projeto para responder. O filtro especializado `unlinked=true`
continua reservado a `chat:link`.

O ícone e o menu operacional do Chat só aparecem quando `/chat/channels` retorna
uma conexão acessível. A interface revalida esse acesso periodicamente e elimina
a seleção ao perder acesso. Gestores podem selecionar participantes pelo item
Configurações → Conectores, sem acesso às mensagens de outras equipes.

O grupo é mantido em `chat_team` / `chat_team_member`, não nas equipes de Vendas
(`team` / `team_member`). Cada conexão tem seu grupo exclusivo; `team_id` continua
gravado em conversas e mensagens, mas referencia esse grupo próprio. Gestores
selecionam `member_ids` entre usuários ativos da organização, incluindo o próprio
usuário para manter acesso administrativo. Alterar participantes não altera o
grupo, o telefone nem os chats. Ser membro ou líder de uma equipe comercial não
concede acesso à instância, e ser administrador não dispensa a participação.

O vínculo usa `BusinessDocument.id`, não o ID nativo da proposta/projeto. Assim,
outros módulos podem reutilizar o mesmo mecanismo. Propostas usam `SALES_QUOTE`;
projetos, `PROJECT`; ordens, `WORK_ORDER`. Contato, cliente e responsável, quando
informados, são validados na organização autenticada.

## Fluxo HTTP

Rotas abaixo são relativas à raiz do backend; aplique o prefixo do proxy e a
autenticação Bearer normalmente usada pelo sistema. Os schemas completos ficam
no OpenAPI da aplicação.

1. `GET /chat/providers`: conectores registrados.
2. `POST /chat/connections`: cadastrar `name`, `provider: "EVOLUTION"`, `base_url`,
   `member_ids`, `external_instance_id` e `api_key`. Segredos têm de 16 a 4096 caracteres.
   `webhook_secret` é opcional: se omitido, o servidor gera um segredo aleatório.
   A resposta não contém credenciais. `configuration` admite apenas
   `timeout_seconds`, de 1 a 60 segundos.
3. `POST /chat/connections/{id}/check`: consultar o estado da instância.
   `POST /chat/connections/{id}/instance` cria a instância;
   `POST /chat/connections/{id}/pairing` obtém o QR Code. As duas ações são
   exclusivas de gerenciadores de conectores e retornam `Cache-Control: no-store`.
   O QR Code não é persistido no banco.
4. `POST /chat/connections/{id}/webhook`: configurar a URL pública e o cabeçalho
   de autenticação na Evolution. Essa operação altera a configuração externa.
5. `POST /chat/conversations`: informar `connection_id`, `business_document_id`,
   `remote_phone` com DDI e DDD; opcionalmente `display_name`, `contact_id` e
   `customer_id`. O mesmo número/canal reutiliza a conversa existente se houver
   acesso, adicionando o vínculo ao documento.
6. `POST /chat/conversations/{id}/messages`: enviar `text` e um UUID
   `client_request_id` gerado para aquela intenção de envio. Reutilizar esse UUID
   e texto ao repetir a requisição; nunca gerar outro só porque ocorreu timeout.

Outras operações:

- `GET /chat/channels`: canais ativos, sem URL ou credenciais do provedor.
- `GET /chat/connections` e `GET/PATCH /chat/connections/{id}`: administração.
- `GET /chat/conversations`: filtros `document_id`, `search`, `status`, `unlinked`.
- `GET/PATCH /chat/conversations/{id}`: detalhes, estado, responsável e contatos.
- `POST /chat/conversations/{id}/links`: adicionar documento relacionado ou
  definir o vínculo principal (`is_primary`).
- `GET /chat/conversations/{id}/messages`: histórico mais recente primeiro.
- `POST /chat/conversations/{id}/read`: zerar não lidos da caixa compartilhada
  local; não envia confirmação de leitura ao WhatsApp.

Listagens de conversas e mensagens aceitam `page` e `page_size` (máximo 100) e
retornam `items`, `total`, `page` e `page_size`.

## Entrega, callbacks e limites

### Histórico e dados da instância

Na aba Conexão, o formulário consulta `GET /chat/connections/{id}/details` para
mostrar telefone, ID externo, nome de perfil quando disponível, integração,
contagens no provedor e no ControlB e data do último callback. A resposta contém
somente campos normalizados; tokens e configurações privadas do provedor não são
retornados. Esse endpoint exige `chat:manage_connectors` e não tem cache.

`POST /chat/connections/{id}/sync` importa uma página de histórico disponível no
provedor. Recebe `page` (inicialmente 1), `page_size` (até 100) e `snapshot_at`
opcional. Retorna `imported`, `existing`, `skipped`, `scanned`, `total`,
`next_page` e `snapshot_at`. Para continuar, reutilize a data e o tamanho da página
com `next_page`; a data limita o histórico consultado para reduzir deslocamentos
causados por mensagens novas. Repetir uma página não duplica mensagens.

Na tela, use Sincronizar recentes e depois Importar próximo lote, se necessário.
O histórico não gera envios nem incrementa não lidas. Os vínculos existentes são
preservados e novas conversas ficam na triagem, visíveis somente a usuários com
`chat:link` (além de `chat:view`). Importar exige essas duas permissões e
`chat:manage_connectors`. Grupos e LIDs sem telefone explícito são ignorados e
contabilizados. O volume informado pelo provedor também inclui registros fora
desse escopo. A importação não solicita ao WhatsApp mensagens que ainda não estão
armazenadas na Evolution.

O painel consulta conversas e a conversa selecionada a cada 5 segundos enquanto
está aberto e a aba está visível. Também possui atualização manual, paginação da
lista e carregamento de mensagens anteriores. Respostas antigas são descartadas
ao trocar de conversa. Sem vínculo com um documento, o envio fica desabilitado.

O contrato foi conferido no [roteamento de consultas da Evolution](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/routes/chat.router.ts)
e na [consulta paginada de mensagens](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/integrations/channel/whatsapp/whatsapp.baileys.service.ts).

O callback é `POST /chat/webhooks/{connection_id}`, autenticado por
`X-ControlB-Webhook-Token`. A organização vem da conexão, nunca do payload.
Eventos repetidos são deduplicados e estados atrasados não regridem uma mensagem
de `READ` para `DELIVERED`. O corpo é limitado a 1 MB e os lotes a 100 eventos.
Somente dados normalizados são armazenados; o corpo original pode conter a chave
do provedor e não é persistido.

O envio guarda a intenção no banco antes da chamada externa. Repetições com o
mesmo UUID retornam o registro existente sem enviar novamente, inclusive quando
concorrentes. Falhas de confirmação, timeout e 5xx mantêm `PENDING` com aviso.
Isso evita repetição automática, mas não garante entrega exatamente uma vez no
WhatsApp. Uma queda entre a persistência e a chamada pode deixar uma intenção
sem envio: confira o provedor antes de iniciar uma nova tentativa. Ainda não há
fila de retomada nem reconciliação automática de envios sem ID externo.

Esta etapa suporta texto em conversas individuais e grupos.
LIDs com `remoteJidAlt` telefônico são normalizados para o mesmo contato.
Conversas individuais em LIDs sem telefone resolvido não são importadas; grupos
preservam o identificador do participante mesmo sem telefone conhecido. Mídias recebidas podem
aparecer como tipo/legenda, sem transferência de arquivos. Informe o telefone
canônico do WhatsApp: resolução de aliases de números ainda não está implementada.
Não há WebSocket nesta etapa; a interface poderá consultar as listagens paginadas.

### Cards, responsável e notificações

Cards mostram nome, última mensagem, contador e uma tag com o nome de perfil do
responsável atribuído. Telefone da instância e vínculo do contato não ocupam o
card; dados adicionais continuam no canal. **⋯ → Atender / Assumir atendimento /
Liberar atendimento** define a tag, independentemente da autoria de cada mensagem.

O sino ao lado do chat configura alertas internos (ativos inicialmente), som e
avisos do navegador (ambos opt-in). Preferências ficam neste navegador por
organização/usuário. Som depende de interação e permissão do navegador; avisos
desktop exigem HTTPS/localhost e consentimento. Não mostram conteúdo ou nomes
na tela bloqueada. Um clique abre o canal e revalida sua permissão.

`GET /chat/notifications` usa a mesma policy das conversas, exclui canais
arquivados/inativos e soma não lidas em todos os canais acessíveis, sem limite
de 50 canais. Sem `since`, retorna somente contador e marco inicial. Com `since`,
retorna novas entradas recebidas ao vivo, paginadas em 100, com `until` estável
e `next_page`. O cliente consulta a cada cinco segundos, sobrepõe dez segundos e
deduplica por ID; a abertura inicial e a importação de histórico não disparam
alertas. O canal em leitura na janela focada não gera alerta. Funciona somente
enquanto o ControlB estiver aberto, inclusive com o widget fechado; não é push
offline e pode sofrer throttling do navegador em segundo plano.

### Grupos WhatsApp

Em **Chat → Conexões → registro → Configuração**, salve a opção **Receber e
responder mensagens de grupos** e clique em **Aplicar configuração e sincronizar
grupos**. `POST /chat/connections/{id}/groups` exige gestão e participação na
instância. Ajusta `groupsIgnore`, preserva as demais opções conhecidas do
provedor, configura os eventos de webhook e consulta os grupos já existentes.
Não cria grupos, não adiciona/remove participantes e não envia mensagens.

Os contratos são os endpoints oficiais de [consulta de grupos](https://docs.evoapicloud.com/api-reference/group-controller/fetch-all-groups)
e de [configurações da instância](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/routes/settings.router.ts).
Os eventos `GROUPS_UPSERT`/`GROUPS_UPDATE` atualizam o nome do grupo; mensagens
usam o JID `@g.us` como canal por instância, nunca como telefone de contato.
`participant`/`participantAlt` identifica quem falou: nome, telefone quando
resolvido e identificador externo por mensagem. Participantes recebidos com
telefone conhecido fazem upsert no Identity, sem vincular o grupo a uma pessoa.
LIDs sem alias preservam a identidade opaca e não geram telefone inventado.

Texto, áudio e histórico usam o mesmo isolamento e idempotência das conversas
privadas. Desabilitar grupos bloqueia novos recebimentos/envios, sem excluir o
histórico. Grupos sem nome no provedor têm identificação provisória até um evento
de nome ou nova sincronização. Recibos de grupos refletem o estado agregado
fornecido pela Evolution; não constituem confirmação individual de cada membro.
A migration `a04c91d367e5` acrescenta campos sem apagar registros existentes.

O formato de envio e de webhook foi conferido no código primário da Evolution:
[SendTextDto](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/dto/sendMessage.dto.ts)
e [configuração de eventos](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/integrations/event/event.dto.ts).
A compatibilidade com a versão instalada deve ser homologada usando uma instância
de teste; os testes automatizados utilizam transporte HTTP simulado, sem mensagens reais.

## Verificação e migrações

### Contato automático e atendimento

Mensagens individuais identificadas por telefone fazem upsert do contato na
organização. Telefone formatado e número canônico reutilizam o mesmo cadastro;
conflitos entre contatos preexistentes são recusados para revisão, sem fusão
silenciosa. Nome de mensagem enviada pelo atendente nunca nomeia o contato.
Nomes editados manualmente são preservados. Conversas de instâncias distintas
continuam separadas e mensagens gravam equipe e telefone da instância.

No widget, Abertas / Fechadas / Arquivadas usam `status=OPEN|CLOSED` e
`archived=true|false`. `PATCH /chat/conversations/{id}` permite:

- `status`: fechar registra `closed_at` e `closed_by_id`; reabrir limpa esses campos.
- `is_archived`: independente do estado; não exclui histórico nem modifica o contato.
- `assigned_user_id`: assumir/liberar; o responsável deve pertencer à equipe.

Enviar exige conversa aberta e não arquivada. Mensagens recebidas continuam
armazenadas mesmo com o atendimento fechado/arquivado, sem mudar esses estados
automaticamente. Ações de atendimento não são bloqueadas por um contato inativo.

`GET /chat/conversations/{id}/contact` retorna o contato acessível pela conversa.
`PATCH /chat/conversations/{id}/contact-origin` recebe `origin_id` (ou `null` para
limpar) ou `name` para criar/reutilizar uma origem inline. A origem pertence ao
**contato**, vale em todas as suas conversas e não transfere acesso entre equipes.
Clientes e fornecedores permanecem cadastros próprios, sem promoção implícita.
`e82a7fb145c3` adiciona a referência opcional de Fornecedor para Contato, sem alterar
registros existentes; `d71f6ea034b2` fornece os campos de equipe e atendimento.

### Continuidade ao substituir uma instância técnica

A conexão do ControlB é o cadastro estável: o ID da sessão/instância da Evolution
pode mudar sem alterar os IDs das conversas e mensagens. Para uma instância nova
com o mesmo número, edite o servidor/identificador/credencial **na conexão original**
em Chat > Conexões > Configuração. A instância de destino precisa estar previamente
pareada. O PATCH confirma o número pelo provedor antes de aceitar a substituição,
mantém a equipe e o checkpoint, configura o webhook e renova seu segredo. Eventos
com o segredo antigo deixam de ser aceitos. Falhas de validação ou configuração
desfazem a alteração local; não existe transação distribuída com o provedor.

Outro número exige outro cadastro. Confirmar o mesmo telefone em um segundo
cadastro da mesma organização é bloqueado para evitar históricos fragmentados;
não há fusão automática de conexões nem transferência de histórico entre equipes.
O mesmo contato em dois números de atendimento mantém um contato no Identity,
mas possui conversas independentes. O grupo interno é estável; seus participantes
podem ser alterados mesmo após existir histórico. Administradores também precisam
pertencer ao grupo para acessar as mensagens.

O formulário oferece seleção direta de usuários, sem seletor de equipes comerciais.
A migration `f93b80c256d4` separa os grupos das conexões existentes, preserva os
chats e não copia permissões de Vendas. Configure os participantes explicitamente
após essa atualização. Conexões sem participantes ativos podem ser configuradas
por gestores da organização; isso não concede leitura de mensagens antes do vínculo.
O checkpoint é preservado e a recuperação fica sinalizada; isso **não implementa
um worker de recuperação automática**, que permanece uma etapa posterior.

### Áudio, transcrição local e links (itens 5 e 6)

Conversas continuam isoladas pela conexão lógica e pelo telefone da instância,
com snapshots de equipe e número nas mensagens. Leitura, fechamento e arquivamento
de um canal não alteram outro canal do mesmo contato. Mensagens de saída não
fornecem nome de contato; mensagens recebidas usam `pushName`, com fallback para
`profileName`, preservando nomes preenchidos manualmente no Identity. O parser
reconhece os envelopes `ephemeralMessage` e `viewOnceMessage*`.

O widget mostra links HTTP(S) clicáveis, incluindo `www`, escapando o texto e
abrindo outra aba com `noopener noreferrer`. Não executa HTML nem busca previews
Open Graph automaticamente.

`GET /chat/messages/{id}/audio` verifica organização, participação no grupo da
instância e acesso aos documentos da conversa. Busca a mídia pelo ID da mensagem
na instância autorizada, via `getBase64FromMediaMessage`, nunca por uma URL
escolhida pelo navegador. A resposta não é cacheada. Limites: 20 MiB de áudio,
28 MiB de resposta JSON, MIME de áudio permitido e nenhum redirecionamento HTTP.
O áudio é carregado no widget somente ao clicar, com revogação da URL temporária
quando a mensagem é desmontada. A disponibilidade depende da mídia no provedor;
expiração ou substituição de uma instância técnica pode impedir downloads antigos.

Transcrição é opcional por conexão (`transcription_enabled`, padrão `false`).
Para habilitar no servidor, no ambiente virtual:

```powershell
python -m pip install -e ".[speech]"
```

Disponibilize um modelo **faster-whisper/CTranslate2** completo em pasta local
(incluindo `model.bin`, configuração e tokenizer) e configure
`CHAT_STT_MODEL_PATH` com seu caminho absoluto. Não é um arquivo `.pt` do Whisper.
O modelo não é baixado automaticamente. Reinicie o backend e marque
“Transcrever áudios automaticamente” em Chat → Conexões → Configuração.
`GET /chat/audio/runtime` permite ao gestor conferir se o pacote/pasta básica e
o worker estão disponíveis; esse diagnóstico não substitui carregar e testar o
modelo. `CHAT_AUDIO_WORKER_ENABLED=false` desativa o consumidor.

Novos áudios entram em `PENDING` e o worker local transcreve em CPU/int8, limitando
a decodificação a dez minutos. O texto fica em `transcription`, sem substituir
o conteúdo original. Há bloqueio transacional por mensagem para impedir
processamento concorrente duplicado. Estados: `NOT_REQUESTED`, `NOT_CONFIGURED`,
`PENDING`, `DONE`, `FAILED`. Falhas não interrompem o webhook nem os demais chats;
o botão Transcrever/Tentar novamente usa
`POST /chat/messages/{id}/transcribe` (exige `chat:send` e participação).
`GET /chat/messages/{id}/transcription` acompanha o resultado com a mesma política
de leitura; permite atualizar também áudios carregados de páginas anteriores.
Texto transcrito é automático e pode conter imprecisões. Áudios não são enviados
a um provedor externo de IA. A suíte simula o STT; instalar o motor/modelo e
validar fala real ainda é necessário no ambiente de destino.

Este worker processa **somente áudio**; não implementa recuperação automática
de mensagens perdidas na reconexão, que permanece adiada.

### Navegação Identity e Contatos (rotas)

`/cadastros` volta a renderizar o Identity (a rota ausente caía no redirecionamento
genérico para o Dashboard). Módulos → Contatos e Identity → Contatos abrem
`/contatos`, reutilizando a tabela `contact`, sem cadastro paralelo. A lista mostra
contatos da organização, origens e vínculos comerciais, com busca, paginação e
filtros por instância, origem do cadastro e status. Os canais exibidos são apenas
os acessíveis ao usuário; o contato organizacional permanece visível mesmo sem
acesso às suas conversas. `/contatos/novo` e `/contatos/{id}` usam formulário de
registro com abas Dados / Origens e vínculos, sem wizard. O filtro `contact_id`
de `/identity/contact-directory` obedece à mesma delimitação por organização.

As migrations `b59d4c8e12f0` e `c60e5d9f23a1` criam as tabelas e o identificador
idempotente de envio. Execute `alembic upgrade head` no ambiente de destino com
backup e o procedimento normal de implantação. A suíte usa banco PostgreSQL
efêmero; testa upgrade/downgrade em schema transacional isolado, permissões,
validação, callbacks, concorrência, estados de entrega e falhas de transporte.
