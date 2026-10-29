# 📊 PriceRadar AI — Monitor Inteligente de Preços & Recomendações de Compra

Um sistema completo e automatizado para **monitorar produtos em lojas confiáveis brasileiras**, registrar o histórico temporal de preços, calcular estatísticas de mercado e **definir o melhor momento para comprar**, enviando alertas e relatórios diários via **Telegram** e **n8n**.

---

## 🚀 Principais Funcionalidades

1. **Varredura em Lojas Confiáveis:**
   - Coleta ofertas de lojas como **Amazon Brasil, Mercado Livre, Magazine Luiza, KaBuM!, Fast Shop, Casas Bahia** e agregadores de mercado.
   - Filtro inteligente de falsos positivos (remove acessórios/capinhas que distorcem o menor preço).
2. **Motor de Inteligência do "Melhor Momento de Compra":**
   * 🟢 **Excelente Momento (Comprar Agora):** Identifica se o produto atingiu a **mínima histórica**, se teve queda repentina $\ge 7\%$ em relação à média recente ou se atingiu o **preço-alvo** estipulado por você.
   * 🟡 **Preço Estável / Normal:** Preço oscilando dentro da média usual.
   * 🔴 **Preço Alto / Aguarde:** Identifica altas repentinas ou preços acima da média semanal.
3. **Painel Web Moderno (Glassmorphism Dark Theme):**
   - Cards dinâmicos com foto do produto, menor preço, loja correspondente e variação percentual vs ontem ($\Delta\%$).
   - Gráfico de linha interativo em Canvas renderizando o histórico de oscilação e linha guia da meta de preço.
   - Botão **"🔍 Testar Busca ao Vivo"** ao cadastrar novos produtos para validar as ofertas antes de salvar.
   - Botão **"🔄 Verificar Agora"** para disparar varredura imediata em tempo real.
4. **Relatórios Automáticos no Telegram:**
   - Mensagens ricas formatadas em HTML com emojis, links diretos de compra, resumo de variação e veredito do dia.
5. **Integração Pronta com n8n:**
   - Workflows JSON incluídos para agendamento diário automático às 08:00 AM e comandos interativos no chat (`/produtos`, `/verificar`).

---

## 📁 Estrutura do Projeto

```text
price-monitor-bot/
├── backend/
│   ├── app/
│   │   ├── analyzer.py            # Motor estatístico e decisão de compra (🟢/🟡/🔴)
│   │   ├── config.py              # Configurações e variáveis de ambiente
│   │   ├── database.py            # SQLite com conexão segura WAL e foreign keys
│   │   ├── main.py                # FastAPI REST API e servidor de arquivos estáticos
│   │   ├── models_repo.py         # Repositório de dados (CRUD e histórico)
│   │   ├── schemas.py             # Modelos de validação Pydantic
│   │   ├── scraper.py             # Coletor multi-lojas e normalizador de preços
│   │   ├── seed_data.py           # Seeder com histórico realista de 14 dias
│   │   └── telegram_bot.py        # Envio de relatórios e mensagens Telegram
│   └── requirements.txt
├── frontend/
│   ├── css/
│   │   └── style.css              # Design Obsidian Dark com glassmorphism e animações
│   ├── js/
│   │   ├── app.js                 # Lógica de interface, filtros, busca e modais
│   │   └── charts.js              # Gráfico interativo em Canvas (sem dependência externa)
│   └── index.html                 # Página principal do dashboard
├── n8n/
│   ├── workflows/
│   │   ├── daily-price-monitor.json       # Agendamento diário e envio Telegram
│   │   └── telegram-bot-commands.json     # Comandos interativos no chat
│   └── README-N8N.md              # Passo a passo detalhado do n8n
├── .env.example                   # Exemplo de variáveis de ambiente
├── start.bat                      # Inicializador de 1 clique para Windows
└── README.md                      # Documentação completa
```

---

## ⚡ Como Rodar o Projeto

### Opção 1: Inicializador Automático (1 Clique no Windows)
Dê um duplo clique no arquivo:
```cmd
start.bat
```
Ele iniciará o servidor FastAPI e abrirá o painel automaticamente em:
👉 **http://127.0.0.1:8000**

---

### Opção 2: Pelo Terminal

1. Abra o terminal na pasta do projeto:
```bash
cd price-monitor-bot/backend
```

2. Instale as dependências (se ainda não tiver instalado):
```bash
python -m pip install -r requirements.txt
```

3. Inicie o servidor:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

4. Abra no navegador:
👉 **http://127.0.0.1:8000**

---

## 🤖 Como Configurar o Telegram

1. Abra o Telegram e procure por **`@BotFather`**.
2. Envie o comando `/newbot` e siga as instruções para criar seu bot.
3. Copie o **Token HTTP** fornecido (ex: `7182938472:AAFlk...`).
4. Abra o bot **`@userinfobot`** no Telegram e envie qualquer mensagem para descobrir o seu **Chat ID** (ex: `987654321`).
5. No painel web (**http://127.0.0.1:8000**), clique no botão **"⚙️ Telegram & n8n"** no topo.
6. Cole o Token e o Chat ID e clique em **"🔔 Enviar Mensagem de Teste"**.
7. Pronto! Você receberá a confirmação imediatamente no seu Telegram.

---

## 🔄 Como Usar com o n8n

1. No terminal, inicie o n8n:
```bash
npx n8n
```
2. Acesse **http://localhost:5678**.
3. Vá em **Workflows** > **Import from File** e selecione:
   `n8n/workflows/daily-price-monitor.json`
4. Conecte sua credencial do Telegram no nó correspondente e ative o workflow (**Active**).
5. O n8n fará a varredura todos os dias às 08:00 AM e mandará o relatório detalhado no seu Telegram!

---

## 📡 Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/products` | Lista todos os produtos com último preço e status |
| `POST` | `/api/products` | Cadastra novo produto e dispara 1ª busca |
| `POST` | `/api/products/{id}/check` | Dispara varredura imediata para um produto |
| `POST` | `/api/check-all` | Dispara varredura em todos os produtos (usado pelo n8n) |
| `GET` | `/api/products/{id}/history` | Retorna histórico diário de preços para os gráficos |
| `POST` | `/api/search-preview` | Testa uma busca ao vivo sem salvar |
| `GET` | `/api/dashboard/stats` | Resumo de métricas do dashboard |
| `POST` | `/api/telegram/test` | Envia mensagem de teste para o Telegram |
| `GET` | `/api/n8n/export-workflow` | Baixa o arquivo do workflow n8n |
