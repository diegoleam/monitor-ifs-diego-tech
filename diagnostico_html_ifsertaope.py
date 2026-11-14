"""Diagnóstico somente leitura do HTML público de editais do IFSertãoPE."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import requests

URL = 'https://ifsertaope.edu.br/editais/'

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href = dict(attrs).get('href')
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            self.links.append((self._href, ' '.join(' '.join(self._text).split())))
            self._href = None
            self._text = []

def main():
    try:
        r = requests.get(URL, headers={'User-Agent':'MonitorIFs-DiegoTech/diagnostico (consulta publica)', 'Accept':'text/html'}, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        print('ERRO DE REDE:', type(exc).__name__, str(exc)[:250]); return
    html = r.text
    print('URL solicitada:', URL)
    print('HTTP:', r.status_code)
    print('URL final:', r.url.split('?')[0])
    print('Content-Type:', r.headers.get('Content-Type', 'nao informado'))
    print('Caracteres HTML:', len(html))
    blocked = any(x in (r.url + ' ' + html[:8000]).lower() for x in ['validate.perfdrive.com','radware captcha','captcha page','botmanager_support@radware.com'])
    print('Indicador de bloqueio:', 'SIM' if blocked else 'NAO')
    for number in ['152/2026', '151/2026', '128/2026', '127/2026']:
        pattern = rf'(?<!\d){number.split("/")[0]}\s*(?:/|&#47;|\\u002f)\s*2026'
        print('Edital', number, 'no HTML:', 'SIM' if re.search(pattern, html, re.I) else 'NAO')
    parser = Links()
    parser.feed(html)
    print('Quantidade de links HTML:', len(parser.links))
    internal = [(urljoin(r.url, href), text) for href, text in parser.links if urlparse(urljoin(r.url, href)).netloc == 'ifsertaope.edu.br']
    print('Links internos:', len(internal))
    print('Amostra de links relevantes (maximo 20):')
    count = 0
    for link, title in internal:
        if any(x in (link + ' ' + title).lower() for x in ['edital','152','151','128','127']):
            print('-', (title or '(sem texto)')[:110], '|', link[:200])
            count += 1
            if count >= 20: break
    print('Links relevantes exibidos:', count)
    print('Diagnostico concluido; nenhum arquivo de estado alterado.')

if __name__ == '__main__':
    main()
