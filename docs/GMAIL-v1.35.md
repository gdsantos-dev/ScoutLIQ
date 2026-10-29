# Gmail OAuth e configuração — v1.35

18/10/2026. API oficial implementada em `gmail_adapter.py`/`gmail_oauth.py`. Credenciais reais não fornecidas; todos os testes são controlados. Não usar Gmail conectado ao ChatGPT, automação de navegador ou credenciais de QA na operação.

## Configuração explícita

Criar cliente OAuth de aplicativo web no Google Cloud e habilitar Gmail API. Registrar exatamente `APP_ORIGIN/api/communication/gmail/callback` como redirect. Produção exige HTTPS; HTTP somente para localhost/127.0.0.1 em desenvolvimento. Definir no ambiente privado do servidor:

```
GMAIL_ENABLED=true
GMAIL_CLIENT_ID=<cliente próprio>
GMAIL_CLIENT_SECRET=<segredo próprio>
GMAIL_REDIRECT_URI=https://seu-dominio/api/communication/gmail/callback
COMMUNICATION_TOKEN_KEYS=<chave Fernet própria>
OUTREACH_DAILY_SEND_LIMIT=<limite de 1 a 100>
OUTREACH_MIN_INTERVAL_SECONDS=60
OUTREACH_ALLOWED_MARKETS=<países revisados, separados por vírgula>
```

Também adicionar `"gmail":N` ao JSON existente `RESEARCH_PROVIDER_DAILY_LIMITS`, sem remover os outros provedores; confirmar RESEARCH_HTTP_DAILY_BUDGET e RESEARCH_DAILY_BUDGET. Refresh, leitura, reconciliação e envio usam a mesma cota de operações Gmail da instalação. O supervisor/worker deve compartilhar banco, configuração e chave de cifra com o servidor web. Padrões são envio desabilitado, limite zero, nenhuma jurisdição e nenhuma operação Gmail autorizada.

Gerar chave com a biblioteca `cryptography.fernet.Fernet.generate_key()` em ambiente privado. Não copiar uma chave sintética de teste. Guardar fora do banco e do Git em secret manager/variável protegida; manter backup protegido. Sem chave correta o sistema falha fechado. Até três chaves Fernet podem ser configuradas, atual primeiro: novas gravações usam a atual e leituras tentam o conjunto. Não remover uma chave antiga enquanto houver registros cifrados por ela; reconectar as contas/renovar credenciais e preservar backup antes de retirar a chave. Não existe rotação em lote automática.

## OAuth e credenciais

POST connect exige sessão e CSRF. Gera state aleatório (somente hash no banco), validade de dez minutos, vínculo ao usuário e hash da sessão e verifier PKCE cifrado. Callback GET consome state atomicamente **antes** da troca, mesmo quando a troca falha. Código e token nunca são devolvidos à UI. Redirect fornecido pelo navegador não é aceito. A troca inclui S256/verifier sem fallback silencioso; suporte no cliente web efetivamente cadastrado precisa ser homologado. Documentação Google descreve explicitamente PKCE para clientes instalados; isso não equivale a homologação deste cliente web.

Scopes solicitados: **gmail.send + gmail.readonly**. Não solicitar `mail.google.com`, escrita/alteração da caixa ou exclusão. Readonly é necessário para conteúdo das respostas e reconciliação; gmail.send sozinho não concede users.getProfile. Consentimento parcial falha fechado. A identidade é obtida pelo perfil Google após troca. Reconexão exige a mesma identidade, altera versão e cancela autorizações anteriores; novas contas são limitadas a três por usuário.

Refresh/access tokens ficam cifrados com Fernet/MultiFernet da biblioteca fixada `cryptography==50.0.2`, com vínculo cifrado ao usuário+ID da conta. Renovação ocorre fora de transação, com fence de versão antes de persistir. Expiração/revogação exige reconexão; erros não armazenam o corpo da resposta nem credenciais. Desconexão cancela pendências e remove credenciais locais antes da revogação remota. Se o provedor não confirmar revogação, a UI informa a necessidade de remover o acesso nas permissões da Conta Google.

Endpoints fixos HTTPS, sem redirects de transporte, sem URL fornecida pelo usuário, timeout de 15s e resposta limitada a 2MB. Envio MIME apenas texto, remetente primário, Message-ID persistente. Não há retry automático de POST send. Caminhos por IDs de provedor têm validação estrita.

Access log do Uvicorn remove query do callback; resposta usa no-store e no-referrer. **Configurar também o proxy/host para não registrar query strings nesse caminho**, pois a aplicação não controla logs anteriores ao processo. Nunca registrar Authorization, corpos OAuth ou MIME. Sem implementação de webhook nesta versão.

## Homologação externa obrigatória antes de operação

1. Verificar configuração OAuth e requisitos de verificação/consentimento com o uso pretendido. `gmail.send` é sensível e `gmail.readonly` restrito; leitura/armazenamento servidor pode exigir verificação/avaliação de segurança, conforme exceções e modalidade aplicáveis.
2. Conferir login, consentimento parcial/negado, state/PKCE, perfil, refresh, revogação e reconnect com conta de teste autorizada.
3. Conferir SPF/DKIM/DMARC/reputação do remetente, revisão de jurisdição, consentimento e remoção; habilitar limites pequenos.
4. Só após autorização explícita do operador realizar um envio de homologação para destinatário autorizado. Conferir aceitação, timeout/reconciliação e resposta. Não usar os testes automatizados para disparos reais.
5. Homologar host HTTPS, cookies, proxy, volume/banco, backups, observabilidade sem conteúdo sensível e interrupção do worker.

Nenhuma dessas verificações externas foi executada nesta entrega. Testes locais demonstram contratos e guardas, não aprovação do Google ou qualidade comercial.

## Fontes oficiais consultadas

- [Escopos Gmail](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Verificação de escopos restritos](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Authorization Code para servidor web](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Boas práticas OAuth](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
- [PKCE em apps instalados](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Perfil Gmail](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile)
- [Envio](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send)
- [Busca de mensagens](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- [Histórico incremental](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- [Sincronização e expiração do cursor](https://developers.google.com/workspace/gmail/api/guides/sync)
- [Fernet/MultiFernet](https://cryptography.io/en/stable/fernet/)
