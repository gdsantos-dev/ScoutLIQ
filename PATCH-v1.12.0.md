# ScoutLIQ v1.12.0 — Score Engine 2.0 · Parcela 2/5

## 1. Contexto por nicho antes da pontuação

O Score Engine 2.1 passa a inferir, de forma determinística e auditável, o contexto comercial do estabelecimento a partir da categoria e, apenas como fallback secundário, do nome. A inferência não usa LLM e sempre expõe a confiança da classificação.

Perfis iniciais:

- Saúde e clínicas;
- Alimentação;
- Beleza e estética;
- Automotivo;
- Varejo;
- Hospedagem;
- Fitness e bem-estar;
- Educação;
- Imobiliário;
- Serviços profissionais;
- Serviços locais;
- Negócio local genérico quando não houver evidência suficiente.

Cada perfil possui requisitos comerciais próprios. Exemplos: agendamento em clínicas e beleza, cardápio em alimentação, estoque em automotivo, catálogo de imóveis em imobiliárias e contato estruturado em serviços profissionais.

Requisitos específicos **só alteram o score depois de uma auditoria real do site**. Se o dado não foi verificado, o estado fica `unknown` e vale zero. O Scout não transforma ausência de dado em problema inventado.

## 2. Diagnóstico estruturado

O score agora retorna uma lista `diagnosis` separada das razões numéricas. Cada problema contém:

- chave estável;
- área afetada;
- severidade (`high`, `medium`, `low`);
- título;
- explicação;
- evidências;
- sugestões estruturadas de tipos de serviço que podem resolver o problema.

O perfil compacto do lead passa a guardar também as chaves/severidades das descobertas da auditoria e o sinal de WhatsApp encontrado dentro do site. Isso permite reconstruir diagnósticos sem reler o relatório completo a cada renderização.

A ficha da oportunidade mostra o contexto do nicho, requisitos detectados/não detectados e os principais problemas verificados antes das informações genéricas da empresa.

## Score Engine

Versão das regras: `2.1`.

As quatro dimensões continuam limitadas a 100 pontos no total:

- Necessidade digital: 50;
- Demanda pública: 20;
- Facilidade de contato: 20;
- Atividade digital: 10.

O contexto de nicho não cria uma quinta dimensão. Ele melhora a interpretação da necessidade digital usando evidência auditada.

## Banco de dados

Nenhuma migração nova. A estrutura adicionada na migração `012` já suporta os dados compactos usados nesta parcela.
