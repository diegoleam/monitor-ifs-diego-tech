"""COMPEC IFPB: processos recentes, tabelas de publicações e links oficiais.

Compatível com monitor.common da série v3; não altera histórico nem Telegram.
"""
import os
import re
from urllib.parse import urljoin, urlparse

from monitor.common import LOG, canonical, clean, fetch, identifier

ROOT = 'https://concursos.ifpb.edu.br/'
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
PAT = re.compile(r'/(?:processos_seletivos|editais)/concurso/(' + UUID + r')(?:/|$)', re.I)
REFERENCE = ROOT + 'processos_seletivos/concurso/beab9b5a-0554-4ee8-8f8e-6e959520deb9/'
EXT = re.compile(r'\.(?:pdf|docx?|xlsx?|odt|ods|csv|zip|rar)(?:$|[?#])', re.I)
DOWNLOAD = re.compile(r'/(?:download|downloads|arquivo|arquivos|anexo|anexos|file|files|media|storage)(?:/|$)', re.I)
DATE = re.compile(r'\b\d{2}/\d{2}/\d{4}(?:[, ]+\d{2}:\d{2})?\b')
DOC_WORDS = re.compile(r'\b(?:edital|retifica(?:ção|cao)|resultado|homologa(?:ção|cao)|convoca(?:ção|cao)|publica(?:ção|cao)|comunicado|recurso|inscri(?:ção|cao|ções|coes)|lista|classifica(?:ção|cao)|deferid[oa]s?|indeferid[oa]s?|gabarito|prova|anexo|portaria|cronograma|aviso|nota|termo|ata|rela(?:ção|cao))\b', re.I)
SKIP = ('/login', '/logout', '/faq', '/cadastro', '/entrar', '/contato')


def process_url(uid):
    return urljoin(ROOT, 'processos_seletivos/concurso/' + uid.lower() + '/')


def official(url):
    p = urlparse(url)
    host = (p.hostname or '').lower()
    return p.scheme in ('http', 'https') and (host == 'ifpb.edu.br' or host.endswith('.ifpb.edu.br'))


def processes(soup, base):
    found = {}
    for a in soup.select('a[href]'):
        link = canonical(urljoin(base, a.get('href', '')))
        if urlparse(link).hostname != 'concursos.ifpb.edu.br':
            continue
        m = PAT.search(urlparse(link).path)
        if m:
            uid = m.group(1).lower()
            found[uid] = process_url(uid)
    return found


def pagination(soup, base):
    """Segue apenas paginação explicitamente publicada no HTML, sem adivinhar URLs."""
    urls = []
    for a in soup.select('a[href]'):
        label = clean(a.get_text(' ', strip=True)).lower()
        rel = ' '.join(a.get('rel', [])).lower()
        parent = a.find_parent(class_=re.compile(r'pag(?:ination|inacao)', re.I))
        if not (parent or 'next' in rel or label in ('próximo', 'proximo', 'next', '›', '»') or label.isdigit()):
            continue
        link = canonical(urljoin(base, a['href']))
        if urlparse(link).hostname == 'concursos.ifpb.edu.br' and urlparse(link).path.rstrip('/') == urlparse(base).path.rstrip('/'):
            if link not in urls and link != canonical(base):
                urls.append(link)
    return urls


def extract(soup, url, origin, title):
    found = {}
    scope = soup.select_one('main, #content, .content, article') or soup
    ignored = []
    for a in scope.select('a[href]'):
        raw = (a.get('href') or '').strip()
        if not raw or raw.lower().startswith(('#', 'javascript:', 'mailto:')):
            continue
        link = canonical(urljoin(url, raw))
        path = urlparse(link).path.lower()
        if not official(link) or any(s in path for s in SKIP):
            continue
        if link in (canonical(url), canonical(origin)):
            continue
        # Links de navegação entre abas de processos não são documentos.
        if PAT.search(path) and not (EXT.search(link) or DOWNLOAD.search(path)):
            continue
        row = a.find_parent('tr')
        item = row or a.find_parent(['li', 'article'])
        if item is None:
            item = a.find_parent('div')
        context = clean(item.get_text(' ', strip=True)) if item else ''
        label = clean(a.get_text(' ', strip=True) or a.get('title') or a.get('aria-label'))
        if not label and row:
            label = context[:180]
        if not label:
            label = path.rstrip('/').rsplit('/', 1)[-1] or 'Documento'
        # A COMPEC pode publicar anexos por rotas sem extensão. Aceitar essas
        # rotas somente em linhas/listas de publicações com texto documental.
        direct = bool(EXT.search(link) or DOWNLOAD.search(path))
        structured = bool((row or a.find_parent('li')) and DOC_WORDS.search(context))
        descriptive = bool(DOC_WORDS.search(label) and ('/documentos/' in url or '/editais/' in url))
        if not (direct or structured or descriptive):
            if len(ignored) < 5 and (row or DOC_WORDS.search(context)):
                ignored.append((label[:75], link[:180]))
            continue
        # Nunca transformar links de abas ou paginação em documentos.
        if re.search(r'/(?:processos_seletivos|editais)/concurso/'+UUID+r'/(?:editais|documentos)/?$', path, re.I):
            continue
        if path.rstrip('/') in ('', '/processos_seletivos', '/editais'):
            continue
        date = DATE.search(context)
        key = identifier(origin, link)
        found[key] = dict(portal='COMPEC IFPB', kind='Documento publicado',
                          edital=title, doc=label[:450],
                          date=date.group(0) if date else '', link=link, origin=origin)
    if not found:
        LOG.info('COMPEC diagnostico: secao=%s links=%d amostras_ignoradas=%s',
                 url, len(scope.select('a[href]')), ignored)
    return found


def collect():
    max_pages = max(1, min(5, int(os.getenv('COMPEC_MAX_PAGES', '3'))))
    max_processes = max(1, min(60, int(os.getenv('COMPEC_MAX_PROCESSES', '30'))))
    discovered = {}
    visited = set()
    queue = [ROOT]
    listing_ok = 0
    while queue and listing_ok < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        soup = fetch(url)
        if soup is None:
            continue
        listing_ok += 1
        discovered.update(processes(soup, url))
        for next_url in pagination(soup, url):
            if next_url not in visited and next_url not in queue:
                queue.append(next_url)

    for raw in os.getenv('COMPEC_PROCESS_URLS', REFERENCE).split(','):
        m = PAT.search(urlparse(raw.strip()).path)
        if m:
            discovered.setdefault(m.group(1).lower(), process_url(m.group(1)))

    found = {}
    valid_sections = 0
    for uid, origin in list(discovered.items())[:max_processes]:
        page = fetch(origin)
        if page is None:
            continue
        heading = page.select_one('h1, h2') or page.title
        title = clean(heading.get_text(' ', strip=True)) if heading else 'Processo ' + uid
        for suffix in (f'editais/concurso/{uid}/editais/',
                       f'processos_seletivos/concurso/{uid}/documentos/'):
            section = urljoin(ROOT, suffix)
            sub = fetch(section)
            if sub is None:
                continue
            valid_sections += 1
            found.update(extract(sub, section, origin, title))
    LOG.info('COMPEC: listagens validas=%d processos descobertos=%d secoes validas=%d documentos=%d',
             listing_ok, len(discovered), valid_sections, len(found))
    return found, valid_sections > 0
