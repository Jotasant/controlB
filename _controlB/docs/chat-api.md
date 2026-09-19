# Chat — gateway e API

## Etapa disponível

Backend de conexões, conversas vinculadas a documentos, mensagens de texto e
webhooks. O primeiro adaptador é Evolution API; os serviços usam o contrato
`ChatConnector` e o registro de fábricas, sem importar o adaptador diretamente.
O widget persistente e o formulário de configuração na interface são a próxima
etapa; esta implementação não cria página isolada de chat nem wizard.

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

A instância deve existir e estar pareada na Evolution. Criação de instância e
pareamento por QR não fazem parte desta etapa. O endpoint de configuração de
webhook substitui a configuração de webhook da instância; prefira uma instância
dedicada ao ControlB.

## Permissões e vínculos

- `chat:view`: canais disponíveis, conversas e histórico.
- `chat:send`: envio, combinado com acesso à conversa.
- `chat:link`: criação, classificação, associação e atualização de conversas.
- `chat:manage_connectors`: cadastro, credenciais, teste e configuração de webhook.

O usuário precisa pertencer à organização e ter permissão para visualizar todos
os documentos vinculados à conversa. Uma conversa associada a proposta e projeto
exige acesso aos dois. Conversas recebidas ainda sem vínculo ficam na triagem,
restrita a quem possui `chat:link`, e não permitem envio até a classificação.

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
   `external_instance_id` e `api_key`. Segredos têm de 16 a 4096 caracteres.
   `webhook_secret` é opcional: se omitido, o servidor gera um segredo aleatório.
   A resposta não contém credenciais. `configuration` admite apenas
   `timeout_seconds`, de 1 a 60 segundos.
3. `POST /chat/connections/{id}/check`: consultar o estado da instância.
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

Esta etapa suporta texto em conversas individuais com JID baseado em telefone.
Grupos e LIDs sem telefone resolvido não são importados. Mídias recebidas podem
aparecer como tipo/legenda, sem transferência de arquivos. Informe o telefone
canônico do WhatsApp: resolução de aliases de números ainda não está implementada.
Não há WebSocket nesta etapa; a interface poderá consultar as listagens paginadas.

O formato de envio e de webhook foi conferido no código primário da Evolution:
[SendTextDto](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/dto/sendMessage.dto.ts)
e [configuração de eventos](https://github.com/EvolutionAPI/evolution-api/blob/main/src/api/integrations/event/event.dto.ts).
A compatibilidade com a versão instalada deve ser homologada usando uma instância
de teste; os testes automatizados utilizam transporte HTTP simulado, sem mensagens reais.

## Verificação e migrações

As migrations `b59d4c8e12f0` e `c60e5d9f23a1` criam as tabelas e o identificador
idempotente de envio. Execute `alembic upgrade head` no ambiente de destino com
backup e o procedimento normal de implantação. A suíte usa banco PostgreSQL
efêmero; testa upgrade/downgrade em schema transacional isolado, permissões,
validação, callbacks, concorrência, estados de entrega e falhas de transporte.
