"""COMPEC IFPB: descoberta de processos UUID e documentos oficiais.

Compatível com monitor.main e monitor.common da v3.x. Não contorna CAPTCHA.
"""
import os
import re
from urllib.parse import urljoin, urlparse

from monitor.common import LOG, canonical, clean, fetch, identifier

ROOT = 'https://concursos.ifpb.edu.br/'
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
PAT = re.compile(r'/(?:processos_seletivos|editais)/concurso/(' + UUID + r')(?:/|$)', re.I)
START = [ROOT, urljoin(ROOT, 'processos_seletivos/')]
REFERENCE = urljoin(ROOT, 'processos_seletivos/concurso/beab9b5a-0554-4ee8-8f8e-6e959520deb9/')
EXTENSIONS = re.compile(r'\.(?:pdf|docx?|xlsx?|odt|ods|csv|zip|rar)$', re.I)
DOWNLOAD_PATH = re.compile(r'/(?:download|downloads|arquivo|arquivos|anexo|anexos|documento|documentos|media|storage)(?:/|$)', re.I)
DATE = re.compile(r'\b\d{2}/\d{2}/\d{4}(?:[, ]+\d{2}:\d{2})?\b')
SKIP = ('/login', '/logout', '/faq', '/cadastro', '/entrar', '/contato')


def process_url(uid):
    return urljoin(ROOT, 'processos_seletivos/concurso/' + uid.lower() + '/')


def processes(soup, base):
    """Aceita links com UUID mesmo que o texto seja 'Ver detalhes'."""
    found = {}
    for a in soup.select('a[href]'):
        url = canonical(urljoin(base, a['href']))
        parsed = urlparse(url)
        if parsed.hostname != 'concursos.ifpb.edu.br':
            continue
        match = PAT.search(parsed.path)
        if match:
            uid = match.group(1).lower()
            found[uid] = process_url(uid)
    return found


def official_link(url):
    host = (urlparse(url).hostname or '').lower()
    return host == 'ifpb.edu.br' or host.endswith('.ifpb.edu.br')


def extract(soup, url, origin, title):
    """Extrai downloads em páginas de editais/publicações; exclui navegação."""
    found = {}
    scope = soup.select_one('main, #content, .content, article') or soup
    for a in scope.select('a[href]'):
        raw = a.get('href', '').strip()
        if not raw or raw.startswith(('#', 'javascript:', 'mailto:')):
            continue
        link = canonical(urljoin(url, raw))
        parsed = urlparse(link)
        path = parsed.path.lower()
        if parsed.scheme not in ('http', 'https') or not official_link(link):
            continue
        if any(x in path for x in SKIP) or link in (canonical(url), canonical(origin)):
            continue
        if PAT.search(path) and not (EXTENSIONS.search(path) or DOWNLOAD_PATH.search(path)):
            continue
        # Endpoints de download podem não ter extensão; não aceitar qualquer link interno.
        is_document = bool(EXTENSIONS.search(path) or DOWNLOAD_PATH.search(path))
        if not is_document:
            continue
        label = clean(a.get_text(' ', strip=True) or a.get('title') or a.get('aria-label'))
        if not label:
            label = path.rstrip('/').rsplit('/', 1)[-1] or 'Documento'
        parent = a.find_parent(['tr', 'li', 'div'])
        context = clean(parent.get_text(' ', strip=True)) if parent else label
        match = DATE.search(context)
        key = identifier(origin, link)
        found[key] = dict(portal='COMPEC IFPB', kind='Documento publicado',
                          edital=title, doc=label, date=match.group(0) if match else '',
                          link=link, origin=origin)
    return found


def collect():
    discovered = {}
    listing_ok = 0
    for url in START:
        soup = fetch(url)
        if soup is None:
            continue
        listing_ok += 1
        discovered.update(processes(soup, url))

    # Referência para diagnóstico: não depende de o índice expor UUIDs.
    seeds = os.getenv('COMPEC_PROCESS_URLS', REFERENCE)
    for raw in seeds.split(','):
        raw = raw.strip()
        match = PAT.search(urlparse(raw).path)
        if match:
            uid = match.group(1).lower()
            discovered.setdefault(uid, process_url(uid))

    limit = max(1, min(60, int(os.getenv('COMPEC_MAX_PROCESSES', '12'))))
    found = {}
    valid_sections = 0
    for uid, origin in list(discovered.items())[:limit]:
        page = fetch(origin)
        if page is None:
            continue
        heading = page.select_one('h1, h2') or page.title
        title = clean(heading.get_text(' ', strip=True)) if heading else 'Processo ' + uid
        sections = [
            urljoin(ROOT, f'editais/concurso/{uid}/editais/'),
            urljoin(ROOT, f'processos_seletivos/concurso/{uid}/documentos/'),
        ]
        for section in sections:
            soup = fetch(section)
            if soup is None:
                continue
            valid_sections += 1
            found.update(extract(soup, section, origin, title))
    LOG.info('COMPEC: listagens validas=%d processos descobertos=%d secoes validas=%d documentos=%d',
             listing_ok, len(discovered), valid_sections, len(found))
    return found, valid_sections > 0
