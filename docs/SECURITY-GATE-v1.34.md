# Revisão de segurança proporcional — v1.34

17/10/2026. Revisão local da fatia P0.2 e regressão herdada. Não é homologação de produção, auditoria jurídica de fontes nem garantia de ausência de vulnerabilidades.

| Área | Verificação/decisão |
|---|---|
| Secrets e ambiente | Chave semântica somente no backend/env, vazia no exemplo. Não é retornada por disponibilidade. Resposta/erro/prompt brutos não vão ao ledger. ZIP de fontes exclui runtime, env real e bancos. |
| Autenticação, sessões, tokens | Rotas usam current_user existente; nenhuma nova autenticação ou credencial no navegador. Expiração/revogação/cookies seguem configuração anterior. Testes herdados passaram. |
| Autorização/IDOR/BOLA | SmartSearch, leads, revisão e contexto mantêm escopo user_id; nenhum ID vindo do modelo. Novo ledger recebe user_id da sessão. Helpers de contexto são internos e usados após fence/ownership existentes. |
| Broken Access Control / escalation / mass assignment | DTO com extra=forbid; modelo só retorna Intent. Sem campos role, owner, billing, autorização de envio ou comandos. Rotinas executam intenção revisada, nunca saída não confirmada do modelo. |
| SQL Injection | ORM/queries parametrizadas. O modelo não produz SQL. SQL literal da migração é constante. |
| NoSQL Injection | Não há banco NoSQL ou filtro remoto livre nesta fatia. JSON validado não vira operador de consulta. |
| XSS | Texto do modelo/contatos renderizado por React, sem HTML bruto. URLs de procedência vêm de páginas coletadas com validação HTTP(S). Não há DOM injection. |
| CSRF/CORS | Endpoint interpret POST usa proteção existente; teste sem token retorna 403. Origens/CORS mantidas. GET de disponibilidade não altera estado nem divulga chave. |
| Abuso/rate limiting/brute force | Login e limites herdados; interpretação limitada por usuário. Reserva persistente global e individual antes de rede, lock serializado, schema/tamanho/timeout e saída limitada. Teste de concorrência admite apenas uma chamada quando resta uma reserva. |
| SSRF/open redirect | Modelo usa origem HTTPS fixa e recusa redirect. WebsiteResearcher mantém controles de DNS/IP/destino/redirect anteriores; auditoria continua no mesmo site. Não foi introduzida URL de provedor configurável pelo usuário. |
| Entradas/terceiros | Schema estrito e validação semântica local; país inferido/critério não suportado exige revisão. HTML e modelo são dados não confiáveis. Host de contato exato impede aceitar wa.me/instagram dentro de outra URL. |
| Upload/path traversal | Nenhum upload/extração de arquivo do usuário foi adicionado na aplicação. Empacotador e patch validam caminhos; extração do baseline conferiu paths antes de escrever. |
| Command injection/deserialização | Sem eval, pickle ou comandos derivados de conteúdo de modelo/site. Scripts de QA usam argumentos fixos e diretório isolado. |
| Headers/HTTPS/clickjacking | Middleware e configuração existentes preservados e cobertos pela regressão. Teste local usa HTTP loopback; HTTPS/HSTS/cookies Secure no host público não foram homologados. |
| Erros/logs/exposição | Falha semântica retorna mensagem fixa com fallback. Exceção externa não é persistida. Ledger tem hash, modelo, reserva, uso e status; contatos públicos ficam restritos à conta. |
| Idempotência/races | Solicitação semântica única por usuário+request_key, reserva serializada, chamada fora de transação, sem retry automático. Reserva incerta não é liberada. Plano/contexto gravados pelo fence do worker existente. |
| Interrupção/recuperação | P0.1 continua protegendo commit após cancelamento/lease; testes de recuperação e supervisor passaram. Modelo em voo pode cobrar mesmo ao fechar modal; fica reservado e não é reenviado pela mesma chave. |
| Pagamentos/webhooks/admin | Nenhuma nova operação financeira, webhook ou endpoint administrativo nesta fatia. OAuth/outbox/replies são pendências explícitas de P0.4, não recursos liberados. |
| Dependências | Nenhuma dependência nova. npm audit completo e de produção, e pip-audit do lock sem vulnerabilidade conhecida no momento da consulta; não equivale a zero risco. |

Não houve uso de credenciais externas reais, envio comercial, alteração de instalação pessoal ou deploy. Antes de produção: confirmar modelo/preços/limites no provedor, retenção aplicável, acesso às fontes, backup consistente, permissões do volume, HTTPS/origem/cookies e readiness no ambiente real. Não habilitar o modo semântico por copiar exemplos de QA.
