"""Diagnóstico somente leitura das tabelas de documentos do IFSertãoPE."""
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

URLS = [
    'https://ifsertaope.edu.br/editais/edital-n-o-118-2026/',
    'https://ifsertaope.edu.br/editais/edital-n-o-152-2026/',
]
HEADERS = {'User-Agent': 'MonitorIFs-DiegoTech/diagnostico (consulta publica)', 'Accept': 'text/html,application/xhtml+xml'}


def testar(url):
    print('\n' + '=' * 75)
    print('EDITAL:', url)
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    except requests.RequestException as exc:
        print('ERRO DE REDE:', type(exc).__name__, str(exc)[:200]); return
    print('HTTP:', response.status_code)
    print('URL final:', response.url.split('?')[0])
    print('Content-Type:', response.headers.get('Content-Type', 'ausente'))
    print('Tamanho HTML:', len(response.text))
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.select_one('table.edital__table')
    print('Tabela edital__table presente:', 'SIM' if table else 'NAO')
    redirected = urlparse(response.url).hostname == 'validate.perfdrive.com'
    print('Redirecionamento para Radware:', 'SIM' if redirected else 'NAO')
    if not table:
        print('Indicadores de bloqueio:', 'SIM' if redirected or 'Radware Captcha Page' in response.text or 'perfdrive.com' in response.text[:5000] else 'NAO/INCONCLUSIVO')
        print('Resultado: SEM TABELA; nao registrar como edital vazio.'); return
    rows = table.select('tbody tr')
    print('Quantidade de linhas:', len(rows))
    for i, tr in enumerate(rows, 1):
        cells = tr.find_all('td', recursive=False)
        if len(cells) < 3:
            print(f'  Linha {i}: formato inesperado ({len(cells)} colunas)'); continue
        a = cells[1].find('a', href=True)
        date = ' '.join(cells[0].stripped_strings)
        title = ' '.join(cells[1].stripped_strings)
        group = ' '.join(cells[2].stripped_strings)
        href = a['href'].strip() if a else '(sem link)'
        print(f'  {i}. Data: {date} | Documento: {title} | Grupo: {group}')
        print(f'     Link: {href}')
    print('RESULTADO:', 'TABELA EXTRAIDA' if rows else 'TABELA SEM LINHAS')

if __name__ == '__main__':
    for url in URLS:
        testar(url)
    print('\nDiagnostico concluido. Sem Telegram, sem gravacao de estado.')
