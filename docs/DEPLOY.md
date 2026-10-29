# Publicar no Railway

> Documento histórico anterior à 1.33. Para a configuração atual, use [DEPLOY-v1.33.md](DEPLOY-v1.33.md): o comando padrão agora supervisiona web e worker juntos. As instruções abaixo de inicialização somente web não se aplicam ao modo combined.

O repositório inclui Dockerfile e railway.toml. A publicação não foi executada por este projeto: requer acesso ao workspace Railway e as variáveis reais da operação.

## Serviço e volume

1. Crie **um novo serviço** para ScoutLIQ no workspace desejado, sem alterar o serviço DashLIQ existente. Aponte para este repositório ou faça upload com Railway CLI após autenticação.
2. Adicione volume persistente montado em `/data`. Use uma réplica. O volume é necessário: o filesystem do contêiner não preserva SQLite entre deploys.
3. Variáveis:

| Variável | Valor |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_ORIGIN` | `https://<domínio Railway gerado>` (depois, domínio customizado exato) |
| `DATABASE_URL` | `sqlite:////data/scoutliq.db` |
| `ADMIN_EMAIL` | E-mail do proprietário |
| `ADMIN_PASSWORD` | Senha exclusiva, 12–256 caracteres |
| `DEMO_SEED` | `false` |
| `RADAR_PROVIDER` | `auto` |
| `RADAR_MAPTILER_API_KEY` | chave pública do MapTiler para o mapa; restrinja por Allowed HTTP origins |
| `RADAR_MAPTILER_STYLE_ID` | `dataviz-v4-dark` por padrão; também aceita o ID de um mapa personalizado |
| `RADAR_GEOAPIFY_API_KEY` | chave criada no projeto Geoapify, somente no backend |
| `RADAR_GEOAPIFY_URL` | `https://api.geoapify.com` |
| `RADAR_HTTP_TIMEOUT` | `8` |
| `RADAR_GOOGLE_LINK_TIMEOUT` | `5`; timeout apenas para resolver links encurtados do Google Maps |
| `RADAR_DETAIL_TIMEOUT` | `4` |
| `RADAR_MAX_RESULTS` | `20` |
| `RADAR_ENRICH_LIMIT` | `8` |
| `RADAR_DETAIL_WORKERS` | `2` |
| `RADAR_LOCATION_TIMEOUT` | `8` |
| `SCOUT_BRAVE_SEARCH_API_KEY` | opcional; habilita busca web ampliada no backend |
| `SCOUT_WEB_SEARCH_TIMEOUT` | `7` |
| `SCOUT_WEBSITE_TIMEOUT` | `5`; timeout por site candidato |
| `SCOUT_WEBSITE_WORKERS` | `4`; paralelismo máximo da validação |
| `SCOUT_WEBSITE_CONFIRM_THRESHOLD` | `62`; confiança mínima para escrever o site no lead |

`PORT` é fornecida pelo Railway. Não criar variáveis `VITE_` com credenciais. `TZ` pode ser configurado, mas os relatórios usam o fuso salvo em Configurações.

4. O Railway detecta o Dockerfile. O build usa `npm ci`, gera estáticos, instala dependências Python travadas e roda como usuário `scout` (UID 10001). Confirme que o volume permite escrita desse usuário. Se o volume montado estiver com proprietário diferente, ajuste a posse do volume por operação administrativa; não mude o web app para root como solução padrão.
5. A inicialização executa `alembic upgrade head` e inicia somente Uvicorn, um worker. Healthcheck `/api/health`. Migrações ocorrem no startup porque o volume não está disponível em etapas separadas de build/predeploy.
6. Confirme HTTPS e origem exata. Entre, cadastre uma operação de teste e verifique persistência após reiniciar o serviço.
7. Remova `ADMIN_PASSWORD` do ambiente após a criação inicial. Para trocar senha use Configurações. Remover/recriar banco exige definir credenciais de bootstrap novamente.

Não configure `scout.orliq.com.br` nesta etapa se quiser manter o domínio Railway. Ao configurar o domínio depois, atualizar `APP_ORIGIN` para ele e validar sessão/CSRF. Não precisa configurar o domínio institucional ou DashLIQ.

## Backup

Com acesso de operador ao ambiente ou cópia local consistente:

```text
python scripts/backup.py --source /data/scoutliq.db --destination /data/backups/scoutliq-YYYY-MM-DD.db
```

O script usa a API de backup SQLite e verifica `integrity_check`; não copie apenas o `.db` enquanto WAL está ativo. Copie o backup resultante para armazenamento privado **fora do volume principal**. Ative backup de volume no Railway se disponível no plano e confirme restauração. Não existe agendamento automático de backup nesta V1; definir rotina antes do uso real.

Para restaurar: pare o serviço, guarde uma cópia do estado anterior, valide o backup numa cópia isolada, substitua o banco com o serviço parado e trate arquivos WAL/SHM associados somente após confirmar caminhos e retenção. Inicie a mesma versão da aplicação, confira a revisão Alembic e os totais. Não regrida esquema automaticamente em produção.

## Memória e custo

Um processo, sem jobs periódicos, sem Redis, sem polling. Mapas renderizam no navegador. Frontend não exige runtime Node. Em produção, `RADAR_PROVIDER=auto` usa Geoapify quando `RADAR_GEOAPIFY_API_KEY` está presente e retorna erro de configuração claro quando a chave está ausente, sem cair silenciosamente no Overpass público. A chave nunca vai ao bundle do frontend. O limite de custo do workspace e do provider é decisão operacional; acompanhar consumo real antes de aumentar volume.

## Atualizações

Backup antes de migrações. Fazer build/testes/auditoria de dependências, publicar e validar health/login/CRUD/persistência. Lock Python cobre runtime; `frontend/package-lock.json` cobre JS. Exemplo de auditoria: `python -m pip_audit -r requirements.lock` e `npm audit --omit=dev`.

O provider de produção está desacoplado pelo contrato `EstablishmentProvider`. Para desenvolvimento sem chave, `RADAR_PROVIDER=osm` ainda habilita Nominatim/Overpass explicitamente, mas isso não é o padrão recomendado para Railway. O autocomplete de município usa o catálogo do IBGE, armazenado em memória por 24 horas; se o catálogo falhar, o campo continua aceitando localização manual. No plano gratuito do Geoapify, mantenha as atribuições exibidas no Radar e monitore a cota do projeto.

Referências: [volumes Railway](https://docs.railway.com/volumes), [FastAPI em contêiner](https://fastapi.tiangolo.com/deployment/docker/), [MapLibre](https://maplibre.org/maplibre-gl-js/docs/), [MapTiler Maps API](https://docs.maptiler.com/cloud/api/maps/), [proteção de chave MapTiler](https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-protect-your-map-key/) e [política de tiles OSM](https://operations.osmfoundation.org/policies/tiles/).


### MapTiler no Radar

Crie uma chave separada no MapTiler Cloud e defina `RADAR_MAPTILER_API_KEY`. Em **Allowed HTTP origins**, informe o host do ScoutLIQ sem protocolo, por exemplo `scoutliq-production.up.railway.app`; ao adotar domínio próprio, inclua-o também. Deixe User-Agent vazio para a chave web. O estilo padrão é `dataviz-v4-dark`, escolhido por reduzir ruído atrás dos pins; `RADAR_MAPTILER_STYLE_ID` pode apontar para `streets-v4-dark` ou para o ID de um mapa customizado da própria conta. A chave é necessariamente entregue ao navegador, por isso a restrição por origem é obrigatória. Sem chave ou se o estilo remoto falhar na inicialização, o ScoutLIQ mantém o fallback MapLibre/OpenStreetMap sem interromper a lista de oportunidades. A CSP libera somente os endpoints necessários ao MapTiler e ao fallback OSM.

## Cadastro, confirmação e recuperação de senha

O ScoutLIQ agora suporta cadastro público com confirmação de e-mail e recuperação de senha. Em produção, configure no Railway:

```text
REGISTRATION_MODE=open
EMAIL_MODE=brevo
BREVO_API_KEY=<chave da Brevo>
EMAIL_FROM_EMAIL=auth@orliq.com.br
EMAIL_FROM_NAME=ScoutLIQ
EMAIL_REPLY_TO=contato@orliq.com.br
```

`APP_ORIGIN` deve apontar para o domínio público real, por exemplo `https://scoutliq.orliq.com.br`, pois ele é usado nos links enviados por e-mail. O remetente configurado em `EMAIL_FROM_EMAIL` precisa estar autorizado/autenticado na Brevo.

Para bloquear novos cadastros temporariamente sem remover a interface, use `REGISTRATION_MODE=closed`. Usuários já existentes continuam entrando normalmente.
