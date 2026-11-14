# Monitor IFs — Diego Tech v3.2

Monitora IFSertãoPE, IFPB e COMPEC, com alertas Telegram assinados **Desenvolvido por Diego Tech**.

## Testes e execução

Instale `pip install -r requirements.txt` e execute `python -m unittest discover -s tests -v`.

Teste manual (envia uma publicação identificada de cada portal, sem alterar histórico):
`python -m monitor.main --mode test-latest --portal all`

Monitoramento com histórico: `python -m monitor.main --mode monitor --portal all`.

## GitHub Actions — importante

O workflow `.github/workflows/monitor-v3.yml` inclui `schedule: */15 * * * *` e execução manual. **O agendamento do GitHub só roda na branch padrão (`main`) e usa o código dessa branch.** Portanto, testar primeiro na branch de desenvolvimento e **só depois integrar o projeto completo na main**. Publicar apenas o YAML na main NÃO instala os coletores novos para o agendamento.

Configure Secrets `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. Permita `Read and write permissions` para o `GITHUB_TOKEN` no repositório, se a política do repositório exigir, para persistir `data/*.json` por commit. Se o push do histórico falhar, o monitor pode repetir alertas em execuções futuras; verifique os logs. O histórico anterior não deve ser apagado.

Na primeira execução automática, os documentos coletados formam a linha de base e não geram avalanche de notificações antigas. Teste manual sempre envia uma mensagem de teste por portal com publicações verificáveis.

## Limitações

IFSertãoPE pode bloquear as páginas individuais com Radware/Perfdrive; reduzir o número de consultas não garante acesso. COMPEC depende de encontrar processos e anexos oficiais acessíveis; um processo de referência é usado para validar a estrutura, mas isso não comprova cobertura integral. O cron é uma solicitação de execução a cada 15 minutos; o GitHub pode atrasar ou pular execuções sob carga.
