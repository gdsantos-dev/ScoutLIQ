# ScoutLIQ 1.21.0 — Mobile Foundation + Login Identity

## Objetivo
Primeiro ciclo pós-redesign da v1.20.0, focado em recuperar usabilidade mobile do shell e refinar a identidade da autenticação sem alterar backend, banco, Score Engine, automações ou contratos de API.

## Login
- Remove a palavra decorativa `SCOUT` gigante do fundo.
- Remove branding duplicado do cabeçalho do login.
- Mantém uma única assinatura ORLIQ no topo e uma única identificação textual `ScoutLIQ` junto da peça visual.
- Botão de login passa de `Entrar no ScoutLIQ` para `Entrar`.
- Símbolo ScoutLIQ passa a ser protagonista em composição 3D responsiva.
- Interação 3D responde a pointer no desktop e ao dedo em dispositivos touch.
- Respeita `prefers-reduced-motion`.
- Recalibra espaçamento, hierarquia, campos, foco e botão principal.

## Shell mobile
- Masthead mobile reduzido de duas linhas/116px para uma linha compacta de 64px.
- Alternância `Operar / Gerir clientes` permanece acessível no topo sem criar uma segunda faixa alta.
- Em telas estreitas, a marca textual recolhe e preserva o símbolo como acionador do menu.
- Command bar permanece disponível por botão dedicado.
- Navegação contextual inferior é mantida, mas com densidade e estados refinados.
- Workspace menu passa a ocupar uma superfície adequada a mobile em vez de um popover estreito ancorado ao desktop.
- Safe areas e posição de notices foram recalibradas.

## Limites deste ciclo
- Radar mobile profundo, CRM/gestão mobile e demais módulos continuam para ciclos posteriores.
- Nenhuma mudança de banco ou migration.
- Nenhuma mudança funcional de autenticação.
