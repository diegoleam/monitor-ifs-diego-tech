# Monitor IFs — Diego Tech v3.0

Três coletores independentes: `monitor/portais/ifsertaope.py`, `ifpb.py` e `compec.py`. Compartilham apenas HTTP, histórico e Telegram em `monitor/common.py`.

## Teste manual no GitHub Actions

1. Coloque os arquivos na raiz do repositório (sem substituir `.git`).
2. Envie para uma ramificação experimental.
3. Para aparecer na aba Actions, registre **somente** `.github/workflows/monitor-v3.yml` na ramificação padrão. O workflow será executado na ramificação selecionada em `Run workflow`.
4. Em Actions > **Monitor IFs v3 - Teste Telegram**, selecione a ramificação experimental e o portal `all`.
5. Os secrets `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` devem existir no repositório.

O teste `test-latest` não modifica arquivos `data/*.json` e envia até três mensagens de teste, uma por portal. Se o portal estiver bloqueado ou sem itens verificáveis, não inventa mensagem. A COMPEC ainda não possui data estruturada: neste caso, a mensagem de teste utiliza o primeiro link relevante da página, **não garante a publicação cronologicamente mais recente**.

## Teste local sem Telegram

`python -m unittest discover -s tests -v`

## Execução de monitoramento (somente após validação)

`python -m monitor.main --mode monitor --portal all`

O modo monitor cria histórico inicial por portal sem enviar publicações antigas; documentos novos em editais já conhecidos podem gerar alerta. O estado `data/<portal>.json` precisa persistir entre execuções, caso contrário a automação não detectará novidades. **Esta versão não ativa agendamento nem commit automático de histórico**. Primeiro valide o Telegram e depois configure a persistência e o agendamento. O `monitor.yml` antigo, se existir no repositório, deve ser desabilitado antes de colocar v3 em produção para evitar execuções paralelas.

### Limitações atuais

- Radware pode bloquear o IFSertãoPE; páginas bloqueadas não são tratadas como vazias.
- A descoberta do IFPB é limitada a links das listagens consultadas, mais o edital 161/2026 como caso conhecido; ampliar os caminhos dos campi após validar.
- A COMPEC utiliza uma heurística de links da página inicial, ainda sem extração comprovada de publicações internas. Não considere seu teste como prova de cobertura completa.
- A coleta é somente leitura; não há contorno de CAPTCHA.

Rodapé de todas as mensagens: **Desenvolvido por Diego Tech**.
