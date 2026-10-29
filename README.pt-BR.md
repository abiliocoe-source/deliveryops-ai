# DeliveryOps AI

Painel de operações de delivery com um pequeno "agente de insights". **Todos os dados incluídos são sintéticos/fictícios.** English: [README.md](README.md).

## Problema
Pequenos deliveries têm dados de pedidos, mas não enxergam rápido atrasos, cancelamentos e diferenças entre categorias, nem o que corrigir primeiro.

## Solução
Envie um CSV (ou use o dataset fictício embutido). O app valida o arquivo, calcula KPIs determinísticos, mostra um dashboard com filtros e gera insights separados em **fatos**, **hipóteses** e **recomendações** (priorizadas por impacto/esforço, sempre com evidência). O relatório exporta para Markdown e CSV.

## Stack e justificativas
| Ferramenta | Por quê |
|---|---|
| Python + Pandas | lógica de KPIs simples e testável |
| Streamlit | UI rápida com filtros, upload e download |
| Plotly | gráficos interativos |
| pytest | testes unitários, incluindo casos extremos |
| `requests` (opcional) | chamar qualquer endpoint LLM compatível com OpenAI |

## Arquitetura
```mermaid
flowchart LR
  CSV[Upload CSV / dados sintéticos] --> V[validação]
  V --> M[métricas: KPIs, por categoria, no tempo]
  M --> I[insights: regras]
  I -. opcional .-> L[resumo LLM + trava de números]
  M --> UI[Dashboard Streamlit]
  I --> UI
  UI --> E[exportação MD / CSV]
```
O LLM nunca calcula nada: só reescreve insights já calculados, e a resposta é descartada se tiver números que não estão na evidência. Sem `LLM_API_KEY` tudo roda localmente por regras.

## Design
Metáfora: quadro de despacho de cozinha com cupons impressos (`assets/style.css`, `ui.py`; fontes Barlow Condensed + IBM Plex Mono). Decisões aplicadas: um KPI dominante (taxa de atraso) com os demais menores numa grade assimétrica; estados de semáforo sempre com palavra e glifo, e metas editáveis na lateral; o cupom do "pior pedido" desenha preparo + entrega contra a marca do prazo prometido; selos FACT / HYPOTHESIS / TO DO com prioridade impacto x esforço; rótulos diretos no gráfico em vez de legenda.

| Desktop 1440 px | Celular 390 px |
|---|---|
| ![desktop](docs/screenshots/desktop-1440-top.jpg) | ![celular](docs/screenshots/mobile-390-top.jpg) |
| ![detalhe](docs/screenshots/desktop-1440-detail.jpg) | ![detalhe celular](docs/screenshots/mobile-390-detail.jpg) |

As capturas foram feitas no Chrome com o app incorporado em exatamente 1440 e 390 px de largura (a janela do navegador não pôde ser reduzida). Foco de teclado e leitores de tela não foram testados com tecnologia assistiva.

## Execução
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
LLM opcional: defina `LLM_API_KEY` (e opcionalmente `LLM_BASE_URL`, `LLM_MODEL`) como variáveis de ambiente (veja `.env.example`). Nunca versione chaves reais.

## Formato do CSV
Colunas: `order_id, order_date, category, status (delivered|cancelled), prep_minutes, delivery_minutes, promised_minutes, rating`. Linhas inválidas (duplicadas, datas ruins, tempos negativos, nota fora de 1-5, status desconhecido) são removidas e reportadas; coluna ausente interrompe a importação com mensagem clara.

## Definições dos KPIs
- **Atrasado**: entregue e `preparo + entrega > promised_minutes`. **Taxa de atraso** = atrasados / entregues.
- **Taxa de cancelamento** = cancelados / todos os pedidos.
- **Tempos médios**: só pedidos entregues. **Nota média**: só pedidos avaliados.
- Denominador vazio retorna `n/a`, nunca um 0 falso.

## Testes
```bash
python -m pytest -q
```

## Resultados medidos (seed 42, 1200 pedidos fictícios)
- 13 testes pytest passam (execução local).
- KPIs do dataset: atraso 8,2%, cancelamento 5,0%, nota média 3,90. Por construção, Pizza tem o maior atraso (16,1%) e o atraso sobe ao longo dos 6 meses. Esses padrões foram colocados pelo gerador; **não** são achados do mundo real.
- O app foi testado de forma automatizada (sem exceções, KPIs renderizam). **Não** foi inspecionado visualmente em navegador.

## Calculadora de economia
Estimativa = pedidos/mês x minutos manuais x parcela automatizada. Sempre rotulada ESTIMATIVA; depende só das suas premissas.

## Integração com LLM: possível, não conectada
Este é um projeto de demonstração de portfólio e roda inteiramente em modo local (só regras). Um adaptador opcional (`llm_summary` em `deliveryops/insights.py`) poderia chamar qualquer endpoint compatível com OpenAI quando `LLM_API_KEY` estiver definida, e descarta qualquer resposta com números que não estejam na evidência. **Nenhuma conexão real com LLM foi feita ou testada**, porque era desnecessária para esta demo. Os testes cobrem só a trava e o fallback sem chave; trate o caminho com LLM como projetado, mas não verificado.

## Limitações
- Dados sintéticos só demonstram o pipeline. Os limiares das regras são heurísticas simples.
- Os insights mostram associação, não causalidade. Sem webhook n8n (omitido por simplicidade).
- Caminho com LLM: projetado, mas nunca conectado a uma API real (desnecessário para a demo); só a trava e o fallback são testados.

## Próximos passos
Análise por hora/região, testes estatísticos entre categorias, alertas via webhook.

## Demo (2 min)
Veja [DEMO.md](DEMO.md).
