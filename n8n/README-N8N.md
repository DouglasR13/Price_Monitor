# 🔄 Guia de Configuração do n8n com o Monitor de Preços

O **n8n** é responsável por orquestrar a rotina diária de monitoramento e enviar os relatórios para o seu Telegram.

---

### 1. Como iniciar o n8n no seu computador

Como você já tem o Node.js instalado, basta abrir um terminal e rodar:

```bash
npx n8n
```

Após alguns segundos, o n8n estará rodando em:
👉 **http://localhost:5678**

---

### 2. Criar seu Bot no Telegram (em 2 minutos)

1. No seu Telegram, busque por **`@BotFather`** e mande `/start`.
2. Digite `/newbot`, escolha um nome (ex: `MeuMonitorPrecosBot`) e um username (ex: `meu_monitor_precos_bot`).
3. O BotFather fornecerá um **Token de Acesso HTTP** (ex: `7182938472:AAFlk...`). Guarde esse token!
4. Para descobrir o seu **Chat ID**:
   - Inicie uma conversa com seu novo bot clicando em "Começar" (`/start`).
   - Em seguida, converse com o bot **`@userinfobot`** no Telegram para ver seu ID numérico (ex: `123456789`).

---

### 3. Importar os Workflows no n8n

1. Acesse **http://localhost:5678** no seu navegador.
2. No menu lateral, clique em **Workflows** > **Add workflow**.
3. No canto superior direito, clique nos três pontinhos `...` > **Import from File**.
4. Selecione o arquivo:
   `price-monitor-bot/n8n/workflows/daily-price-monitor.json`
5. Conecte sua credencial do Telegram:
   - Clique duas vezes no nó **"Enviar Relatório Telegram"**.
   - Em **Credential to connect with**, clique em **Create New**.
   - Cole o token do BotFather e salve.
   - No campo **Chat ID**, informe seu Chat ID.
6. Clique no botão **"Active"** no topo para ativar o agendamento diário automático das 08:00 AM!

---

### 4. Como testar manualmente com 1 clique

No workflow do n8n, você pode clicar em **"Test workflow"** a qualquer momento para rodar a varredura ao vivo e receber as mensagens no seu Telegram instantaneamente!
