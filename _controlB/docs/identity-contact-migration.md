# Contatos canônicos no Identity

## Escopo

Cliente e fornecedor conservam um contact_id opcional, compartilhável por vários
cadastros da mesma organização. Os campos legados continuam fisicamente intactos,
mas respostas HTTP e formulários consultam o Identity. Os endpoints comerciais
rejeitam escrita de dados pessoais e não criam contatos implicitamente.

O cadastro rápido também seleciona o Identity. Criar/editar abre uma página em
outra aba para não perder o formulário comercial; a lista recarrega ao retornar.

Não foram alterados funil, estágios nem envio de mensagens. Na conversão CRM,
somente a fronteira com Identity/Vendas foi ajustada para reutilizar o contato.

## Implantação: não pular o backup

Esta entrega não executa migrações automaticamente. Coloque a aplicação, webhooks
e workers em manutenção durante backup, aplicação e reversão. Use os parâmetros
reais do PostgreSQL do ControlB, não o banco da Evolution.

1. Guarde o backup fora do repositório, em diretório protegido. Não inclua senha
   no comando: use prompt do PostgreSQL ou arquivo pgpass protegido.
2. Exemplo de comandos (substitua HOST, PORTA, USUARIO, BANCO e caminhos):

   ```powershell
   pg_dump -h HOST -p PORTA -U USUARIO -d BANCO -Fc -f "D:\Backups\controlb-antes-contatos.dump"
   pg_restore --list "D:\Backups\controlb-antes-contatos.dump"
   createdb -h HOST -p PORTA -U USUARIO controlb_validacao_contatos
   pg_restore -h HOST -p PORTA -U USUARIO -d controlb_validacao_contatos --exit-on-error "D:\Backups\controlb-antes-contatos.dump"
   ```

3. Verifique contagens e amostras no banco restaurado. Não use --clean, DROP,
   TRUNCATE nem restaure por cima do banco em uso.
4. Revise as revisões pendentes com Alembic antes de atualizar. A nova revisão
   f304b5c6d7e8 adiciona somente contact_identifier e contact_migration_run.
   Seu downgrade preserva essas tabelas; reversão dos dados é uma operação
   separada abaixo. Não faça downgrade das revisões anteriores para esta entrega.
5. Em homologação primeiro, aplique a revisão e simule os dados por organização:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade f304b5c6d7e8
   .\.venv\Scripts\python.exe -m controlb.modules.identity.contact_migration --organization UUID_DA_ORGANIZACAO
   ```

6. Resolva os conflitos apontados no Identity antes de aplicar. A simulação roda
   em savepoint e desfaz todas as suas escritas; não deixa contatos nem vínculos.
   O relatório de saída contém contagens, sem telefone/e-mail.
7. Depois de conferir o relatório e testar a restauração:

   ```powershell
   .\.venv\Scripts\python.exe -m controlb.modules.identity.contact_migration --organization UUID_DA_ORGANIZACAO --apply --backup "D:\Backups\controlb-antes-contatos.dump" --restore-verified
   ```

   A aplicação verifica o arquivo custom do pg_dump e registra SHA-256 e run_id.
   --restore-verified é a confirmação do operador: o programa não presume que
   verificar o cabeçalho do arquivo equivale a testar sua restauração.
8. Repita por organização, confira vínculos e só então libere a aplicação.
   Reexecutar não cria duplicados nem nova execução quando não há alterações.

## Deduplicação e preservação

- Nunca cruza organizações; compara telefone principal, secundário e e-mail.
- Telefone brasileiro nacional usa país BR; internacional usa + ou 00.
  País desconhecido/número ambíguo bloqueia a migração, sem adivinhação.
- E-mail usa trim e casefold, preservando pontos e sufixos +.
- Nome sozinho não identifica a pessoa. Sem telefone/e-mail, um representante
  nomeado pode gerar contato distinto: não há identidade suficiente para fusão.
- Vínculo explícito conflitante, dois contatos correspondentes, valor inválido
  ou valor que exceda o campo de destino abortam a organização inteira.
- Contatos existentes recebem somente campos vazios. Valores alternativos ficam
  nos identificadores; valores de origem completos ficam no journal protegido.
  Nomes/cargos divergentes não sobrescrevem o cadastro canônico.
- Colunas comerciais originais não são apagadas, limpas ou sincronizadas.
- Bloqueio transacional por organização e restrição única nos identificadores
  protegem cadastro manual e WhatsApp contra concorrência.

## Reversão não destrutiva

Faça um novo backup antes da reversão. Primeiro simule:

```powershell
.\.venv\Scripts\python.exe -m controlb.modules.identity.contact_migration --rollback UUID_DA_EXECUCAO
.\.venv\Scripts\python.exe -m controlb.modules.identity.contact_migration --rollback UUID_DA_EXECUCAO --apply --backup "D:\Backups\controlb-antes-reversao.dump" --restore-verified
```

Restaura vínculos anteriores e os campos preenchidos no Identity. Contatos novos
são inativados, nunca apagados; identificadores e auditoria permanecem preservados.
Não é uma exclusão física de todas as evidências da migração. Alterações posteriores
ou novos usos do contato bloqueiam a reversão automática para evitar perda de dados.
O backup permite recuperar o estado integral em banco separado.

A remoção de colunas/tabelas legadas fica para outra entrega, após auditoria,
validação operacional e aprovação explícita. Não há nova dependência.

## Grupos e conversas sem contato

- Entradas e mensagens de grupo não criam Identity Contact.
- Clique no nome do remetente abre/reutiliza conversa na mesma instância:
  POST /chat/conversations/{group_id}/participants/{message_id}/direct.
- O backend deriva o telefone da mensagem armazenada e exige acesso à instância
  e chat:send. Não aceita telefone arbitrário nesse endpoint.
- contact_id fica nulo até mensagem direta recebida; saída/eco não cria contato.
- Mensagens diretas recebidas recuperadas pelo histórico também qualificam.
- Telefone em @s.whatsapp.net ou participantAlt permite abrir; somente @lid
  deixa a ação indisponível. Nunca converta dígitos do LID em telefone.
- Mesmo contato em duas instâncias: dois canais, um cadastro Identity.

## Verificação manual

1. Selecione um contato no cliente e no fornecedor. Salve, edite o nome no
   Identity e reabra ambos: o dado deve ser único. Desvincule um sem afetar o outro.
2. Tente vincular ID de outra organização ou enviar telefone pelo endpoint
   comercial: deve rejeitar, sem criar ou modificar contato.
3. Receba mensagem de participante desconhecido num grupo: nenhum contato novo.
4. Clique no participante e envie mensagem: canal direto sem cadastro.
5. Receba resposta direta: exatamente um contato, vinculado ao mesmo canal.
6. Repita callback/sincronização; envie simultaneamente por duas instâncias:
   um contato, históricos separados e nenhum reenvio.
7. Teste participante @lid com e sem participantAlt; somente o resolvido abre.
8. Em banco restaurado, simule/aplique/repita/reverta a migração e compare os
   campos legados. Edite um contato depois da aplicação: reversão deve bloquear.

Testes usam PostgreSQL isolado. CONTROLB_KEEP_TEST_DATABASE=1 preserva os bancos
de teste; não os remove ao terminar. APP_ENV=test evita o log SQL de desenvolvimento.
