"""Diagnóstico isolado de documentos em páginas individuais do IFSertãoPE."""
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

PAGINAS = [
    'https://ifsertaope.edu.br/editais/edital-n-o-152-2026/',
    'https://ifsertaope.edu.br/editais/edital-n-o-151-2026/',
]
BLOQUEIOS = ('validate.perfdrive.com', 'radware captcha', 'botmanager_support@radware.com')
DATA = re.compile(r'\b(?:[0-3]?\d[/.-][01]?\d[/.-]20\d{2}|20\d{2}[/.-][01]?\d[/.-][0-3]?\d)\b')
PALAVRAS = ('edital', 'resultado', 'homologa', 'retifica', 'publica', 'convoca', 'inscri', 'recurso', 'classifica')

session = requests.Session()
session.headers.update({'User-Agent': 'MonitorIFs-DiegoTech/diagnostico (consulta publica)', 'Accept': 'text/html,application/xhtml+xml'})

for pagina in PAGINAS:
    print('\n' + '=' * 72)
    print('PAGINA:', pagina)
    try:
        resposta = session.get(pagina, timeout=35)
        print('HTTP:', resposta.status_code)
        print('URL final:', resposta.url)
        print('Content-Type:', resposta.headers.get('Content-Type', 'desconhecido'))
        print('Tamanho HTML:', len(resposta.text))
        amostra = resposta.text[:12000].lower()
        bloqueada = any(s in resposta.url.lower() or s in amostra for s in BLOQUEIOS)
        print('Bloqueio detectado:', 'SIM' if bloqueada else 'NAO')
        if bloqueada or resposta.status_code != 200 or 'html' not in resposta.headers.get('Content-Type', '').lower():
            print('Pagina nao analisada por bloqueio ou resposta inesperada.')
            continue
        soup = BeautifulSoup(resposta.text, 'html.parser')
        print('Titulo:', soup.title.get_text(' ', strip=True)[:180] if soup.title else '(ausente)')
        print('PDF 152 resultado presente:', 'Resultado-Preliminar_Edital_152_2026.pdf'.lower() in resposta.text.lower())
        print('Total de links:', len(soup.find_all('a', href=True)))
        candidatos = []
        vistos = set()
        for a in soup.find_all('a', href=True):
            href = urljoin(resposta.url, a['href'])
            if urlparse(href).netloc not in ('ifsertaope.edu.br', 'www.ifsertaope.edu.br'):
                continue
            titulo = a.get_text(' ', strip=True)
            contexto = a.parent.get_text(' ', strip=True)[:350] if a.parent else titulo
            caminho = urlparse(href).path.lower()
            if not ('.pdf' in caminho or '/wp-content/uploads/' in caminho or any(p in titulo.lower() for p in PALAVRAS)):
                continue
            if href in vistos:
                continue
            vistos.add(href)
            datas = DATA.findall(contexto)
            candidatos.append((titulo[:130], href, datas[:4], contexto[:220]))
        print('Links candidatos a documentos:', len(candidatos))
        for i, (titulo, href, datas, contexto) in enumerate(candidatos[:35], 1):
            print(f'  {i}. Titulo: {titulo or "(sem texto)"}')
            print(f'     URL: {href}')
            print(f'     Datas no contexto: {", ".join(datas) if datas else "nenhuma"}')
            print(f'     Contexto: {contexto}')
        print('Observacao: datas do contexto sao indicios, nao datas validadas de publicacao.')
    except requests.RequestException as exc:
        print('Erro de rede:', type(exc).__name__, str(exc)[:250])
print('\nDiagnostico finalizado. Nenhum arquivo de estado foi alterado; nenhum alerta enviado.')
