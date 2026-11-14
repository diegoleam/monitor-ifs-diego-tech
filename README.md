# Monitor IFs — Diego Tech

Monitor experimental de notícias, editais e documentos do IFSertãoPE, IFPB e COMPEC/IFPB.

## Instalação no GitHub (sem computador ligado)

1. Crie um **repositório privado** no GitHub, por exemplo `monitor-ifs-diego-tech`.
2. Envie **todos os arquivos e pastas** deste projeto, incluindo `.github/workflows/monitor.yml`.
3. No Telegram, abra `@BotFather`, envie `/newbot`, escolha nome e usuário e copie o token. **Não compartilhe o token.**
4. Abra a conversa com o bot recém-criado e envie `/start`.
5. Descubra seu chat ID abrindo no navegador `https://api.telegram.org/botSEU_TOKEN/getUpdates` (substitua `SEU_TOKEN`). Procure `message.chat.id`. Não compartilhe a URL com o token.
6. No repositório, vá a **Settings > Secrets and variables > Actions > New repository secret**. Crie `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
7. Vá a **Settings > Actions > General > Workflow permissions**, marque **Read and write permissions** e salve. Confirme que Actions está habilitado.
8. Vá a **Actions > Monitor IFs - Diego Tech > Run workflow**. Confira os logs. A primeira execução cria o histórico sem enviar notícias antigas.
9. Verifique se `data/state.json` apareceu no repositório. O agendamento pede execução a cada 15 minutos; o GitHub pode atrasar ou deixar de executar alguns agendamentos.

## Executar localmente (opcional)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:TELEGRAM_BOT_TOKEN="SEU_TOKEN"
$env:TELEGRAM_CHAT_ID="SEU_CHAT_ID"
python -m monitor.main
```

## Limitações e cuidados

- **Versão experimental**: os seletores e fluxos de navegação dos três portais ainda precisam ser validados em acesso real. O coletor genérico pode perder publicações carregadas por JavaScript, paginação não convencional e PDFs fora do orçamento de downloads.
- A comparação textual pode produzir falsos positivos ou ignorar alterações sutis; PDF é comparado por SHA-256 apenas quando efetivamente baixado.
- `MAX_PAGES_PER_SOURCE` (padrão 8), `MAX_DETAILS_PER_RUN` (45) e `MAX_PDFS_PER_RUN` (12) limitam a carga. A cobertura **não é integral**. Ajuste com cuidado e respeite os sites.
- O robô pode enviar vários avisos relacionados à mesma atualização; a deduplicação usa origem, tipo, URL e hash. Não há agrupamento inteligente de processos nesta versão.
- **Atenção:** alterações detectadas enquanto o Telegram estiver indisponível não são mantidas em fila durável. A versão inicial evita marcar alertas como enviados, mas pode deixar de avisar uma alteração após o histórico ser atualizado.
- O GitHub Actions pode suspender workflows agendados em repositórios públicos inativos e possui cotas; confira as condições vigentes da sua conta.
- Não publique tokens nem chat IDs no código ou em screenshots. Preferir repositório privado.
- Para produção, adicionar testes com páginas reais, rastreamento de paginação por portal, fila persistente e priorização de PDFs.

**Assinatura das mensagens:** Desenvolvido por Diego Tech 🚀
