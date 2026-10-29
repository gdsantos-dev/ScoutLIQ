# Gmail — nota histórica de preparação de P0.4

Esta nota registra o planejamento no checkpoint P0.3. A implementação posterior, suas limitações e a configuração vigente estão em **GMAIL-v1.35.md** e **COMMUNICATION-v1.35.md**. As frases de “a implementar” abaixo descrevem aquele ponto histórico, não o estado final da v1.35.

Consulta oficial em 18/10/2026. **Documento de preparação; OAuth, outbox e sincronização ainda não estão implementados neste checkpoint P0.3.** Não há credencial vinculada nem envio real autorizado.

## Escopos e homologação

A documentação classifica `gmail.send` como sensível e `gmail.readonly`/`gmail.metadata` como restritos. Para ler o conteúdo de respostas, a proposta é `gmail.readonly` junto de `gmail.send`; não solicitar `mail.google.com`, modificação ou exclusão de mensagens. Escopos restritos podem exigir verificação e avaliação de segurança, com exceções dependentes do tipo de uso. A publicação deve avaliar essas condições antes de conectar usuários externos. [Escopos Gmail](https://developers.google.com/workspace/gmail/api/auth/scopes), [verificação de escopos restritos](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

`users.getProfile` aceita leitura/metadata e outros escopos restritos, mas não lista `gmail.send` isolado. Portanto, não pressupor que uma conexão somente de envio possa confirmar a identidade por esse endpoint. `messages.list` permite busca por `rfc822msgid`, porém o parâmetro `q` não pode ser usado com `gmail.metadata`. Para o fluxo completo pretendido, leitura é necessária também para reconciliação e classificação de replies. [Perfil](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile), [lista de mensagens](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list).

## Protocolo proposto

Usar Authorization Code no backend, state aleatório de uso único, validade curta e vínculo à conta/sessão iniciadora. Callback deve validar state antes da troca. Redirect URI deve coincidir com configuração explícita e origem autorizada, sem destino fornecido pelo navegador. Solicitar acesso offline somente para execução autorizada em background; refresh token fica cifrado no servidor, separado da chave de cifra. Tratar revogação/expiração como desconexão, bloqueando envio até reconectar. PKCE S256 deve ser conferido para o cliente escolhido e incluído quando suportado; a documentação de apps instalados o descreve explicitamente, e não deve ser confundida com a configuração de cliente web. [OAuth para servidor web](https://developers.google.com/identity/protocols/oauth2/web-server), [boas práticas](https://developers.google.com/identity/protocols/oauth2/resources/best-practices), [PKCE para apps instalados](https://developers.google.com/identity/protocols/oauth2/native-app).

Essas são decisões de arquitetura a implementar, não comportamento já verificado. Não usar a conexão Gmail do ChatGPT, automação do navegador ou credenciais da QA como credenciais do produto. A biblioteca de criptografia/SDK ainda precisa ser escolhida, instalada, travada e auditada; não criar cifra própria.

## Outbox e sincronização propostas

Persistir mensagem e autorização antes de rede. Um Message-ID determinístico por item ajuda a pesquisar uma tentativa incerta; não fornece garantia de exatamente uma entrega. Timeout depois de possível envio deve entrar em `uncertain`; uma consulta sem resultado não prova que o provedor não aceitou. A resposta de `messages.send` é aceitação técnica, não entrega/leitura/resposta comercial. [Envio](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send).

Para replies, `history.list` usa cursor crescente não contíguo. Cursor fora da retenção pode retornar 404, exigindo resincronização. Persistir deduplicação por conta+message ID e cursor só após a página inteira ser consolidada; paginação deve sobreviver a interrupção. A resincronização proposta será limitada às conversas conhecidas, registrando objetivamente cobertura parcial, sem anunciar sincronização de toda a caixa. [Referência de histórico](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list), [guia de sincronização](https://developers.google.com/workspace/gmail/api/guides/sync).

Associação proposta: conta+thread retornados pelo provedor, Message-ID/References/In-Reply-To e participantes exatos. Assunto ou domínio não bastam. Remover HTML ativo, anexos e conteúdo desnecessário; texto recebido nunca é comando. Classificação conservadora deve separar interesse, pergunta, objeção, recusa, opt-out, autoresposta, bounce e insuficiente. Opt-out suprime destinatário e cancela follow-ups incompatíveis; nenhum retorno autoriza novo envio sozinho.

## Próxima implementação concreta

1. Migração 026: contas de canal, states OAuth, outbox e recibos/replies, todos por usuário; reutilizar OutreachDraft, RecipientPolicy e LeadActivity.
2. Contrato único de adapter, estados e idempotência; nenhuma duplicação de scheduler. Integrar claim/execute ao ResearchExecutor/worker e ledger existentes.
3. Gmail oficial com endpoints fixos, limites de resposta, timeout, cifra, reconnect/revoke, integração mínima em Integrações e ficha.
4. Autorização de envio distinta da aprovação atual: conta remetente, destinatário, canal, conteúdo/versão, condição de contato verificada, vencimento, ator e limites. Validar novamente imediatamente antes da tentativa.
5. Testes controlados de sucesso/erro/replay, expiração, timeout incerto, reconciliação, dedup, opt-out e isolamento; depois homologação externa separada. Não executar envio comercial real nesta missão sem autorização específica.
