"""COMPEC: oportunidades e inscricoes pela tabela oficial, sem duplicar o IFPB.

Interface compatível com monitor.main e monitor.common v3.
"""
import os
import re
from urllib.parse import urljoin, urlparse
from monitor.common import LOG, canonical, clean, fetch, identifier

ROOT = 'https://concursos.ifpb.edu.br/'
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
PAT = re.compile(r'/(?:processos_seletivos|editais)/concurso/(' + UUID + r')(?:/|$)', re.I)
DATE = re.compile(r'^\d{2}/\d{2}/\d{4}$')
REFERENCE = ROOT + 'processos_seletivos/concurso/beab9b5a-0554-4ee8-8f8e-6e959520deb9/'
ACTIONS = {'visitar', 'download', 'baixar', 'abrir', 'acessar', 'visualizar'}


def process_url(uid):
    return urljoin(ROOT, 'processos_seletivos/concurso/' + uid.lower() + '/')


def official(url):
    p = urlparse(url)
    h = (p.hostname or '').lower()
    return p.scheme in ('http', 'https') and (h == 'ifpb.edu.br' or h.endswith('.ifpb.edu.br'))


def processes(soup, base):
    """Mantém a API de descoberta da v3.6."""
    found = {}
    for a in soup.select('a[href]'):
        link = canonical(urljoin(base, a.get('href', '')))
        if urlparse(link).hostname != 'concursos.ifpb.edu.br':
            continue
        m = PAT.search(urlparse(link).path)
        if m:
            found[m.group(1).lower()] = process_url(m.group(1))
    return found


def pagination(soup, base):
    """Apenas paginação que exista no HTML; evita inventar URLs."""
    urls = []
    for a in soup.select('a[href]'):
        label = clean(a.get_text(' ', strip=True)).casefold()
        rel = ' '.join(a.get('rel', [])).casefold()
        parent = a.find_parent(class_=re.compile(r'pag(?:ination|inacao)', re.I))
        if not (parent or 'next' in rel or label in ('próximo', 'proximo', 'next', '›', '»') or label.isdigit()):
            continue
        link = canonical(urljoin(base, a['href']))
        p, b = urlparse(link), urlparse(base)
        if p.hostname == 'concursos.ifpb.edu.br' and p.path.rstrip('/') == b.path.rstrip('/'):
            if link not in urls and link != canonical(base):
                urls.append(link)
    return urls


def listing_items(soup, base):
    """Extrai UUID, título, edital, início, fim e status da MESMA linha."""
    found = {}
    for row in soup.select('table.card-table tbody tr, table.table tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) < 3:
            continue
        uid = None
        for a in row.select('a[href]'):
            link = urljoin(base, a.get('href', ''))
            if urlparse(link).hostname != 'concursos.ifpb.edu.br':
                continue
            m = PAT.search(urlparse(link).path)
            if m:
                uid = m.group(1).lower()
                break
        if not uid:
            continue
        title = clean(cells[1].get_text(' ', strip=True))
        if not title:
            continue
        edital = clean(cells[2].get_text(' ', strip=True))
        start = clean(cells[3].get_text(' ', strip=True)) if len(cells) > 3 else ''
        end = clean(cells[4].get_text(' ', strip=True)) if len(cells) > 4 else ''
        status = clean(cells[5].get_text(' ', strip=True)) if len(cells) > 5 else ''
        found[uid] = dict(title=title, edital=edital, start=start if DATE.fullmatch(start) else '',
                          end=end if DATE.fullmatch(end) else '', status=status)
    return found


def process_item(origin, title, meta=None):
    """Campos existentes são mantidos para o format_message() atual."""
    meta = meta or {}
    edital = clean(meta.get('edital'))
    start, end = clean(meta.get('start')), clean(meta.get('end'))
    status = clean(meta.get('status'))
    doc = 'Edital nº ' + edital if edital else 'Processo seletivo na COMPEC'
    details = []
    if start and end:
        details.append('Inscrições: ' + start + ' a ' + end)
    elif start:
        details.append('Início das inscrições: ' + start)
    elif end:
        details.append('Fim das inscrições: ' + end)
    if status:
        details.append('Situação: ' + status)
    return dict(portal='COMPEC IFPB', kind='Novo processo seletivo',
                edital=title, doc=doc, date='', description=' | '.join(details),
                link=origin, origin=ROOT)


def extract(soup, url, process_link, title):
    """Preserva referências EXCLUSIVAS do Portal do Estudante.

    Links do www.ifpb.edu.br ficam com o coletor IFPB; abas e menus não são publicações.
    """
    found = {}
    scope = soup.select_one('main, #content, .content, article') or soup
    for row in scope.select('tr'):
        cells = row.find_all('td', recursive=False)
        if not cells:
            continue
        values = [clean(c.get_text(' ', strip=True)) for c in cells]
        label = max((v for v in values if v.casefold() not in ACTIONS), key=len, default=title)
        for a in row.select('a[href]'):
            action = clean(a.get_text(' ', strip=True)).casefold()
            raw = (a.get('href') or '').strip()
            if not raw or raw.lower().startswith(('#', 'javascript:', 'mailto:')):
                continue
            link = canonical(urljoin(url, raw))
            host = (urlparse(link).hostname or '').lower()
            if host != 'estudante.ifpb.edu.br' or action not in ACTIONS:
                continue
            key = identifier('compec-ref', process_link, link)
            found[key] = dict(portal='COMPEC IFPB', kind='Inscrição ou referência exclusiva COMPEC',
                              edital=title, doc=label[:450], date='', link=link, origin=ROOT)
    return found


def collect():
    max_pages = max(1, min(5, int(os.getenv('COMPEC_MAX_PAGES', '3'))))
    max_processes = max(1, min(60, int(os.getenv('COMPEC_MAX_PROCESSES', '30'))))
    discovered = {}
    metadata = {}
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
        metadata.update(listing_items(soup, url))
        for next_url in pagination(soup, url):
            if next_url not in visited and next_url not in queue:
                queue.append(next_url)

    # Referências configuradas continuam disponíveis, mas não substituem a listagem.
    for raw in os.getenv('COMPEC_PROCESS_URLS', REFERENCE).split(','):
        m = PAT.search(urlparse(raw.strip()).path)
        if m:
            discovered.setdefault(m.group(1).lower(), process_url(m.group(1)))

    found = {}
    valid_sections = 0
    for uid, origin in list(discovered.items())[:max_processes]:
        meta = metadata.get(uid)
        if meta:
            title = meta['title']
        else:
            page = fetch(origin)
            if page is None:
                continue
            heading = page.select_one('h1, h2') or page.title
            title = clean(heading.get_text(' ', strip=True)) if heading else 'Processo ' + uid
        found[identifier('compec-processo', uid)] = process_item(origin, title, meta)
        for suffix in (f'editais/concurso/{uid}/editais/',
                       f'processos_seletivos/concurso/{uid}/documentos/'):
            section = urljoin(ROOT, suffix)
            sub = fetch(section)
            if sub is None:
                continue
            valid_sections += 1
            found.update(extract(sub, section, origin, title))
    LOG.info('COMPEC: listagens validas=%d processos descobertos=%d secoes validas=%d oportunidades=%d titulos_da_tabela=%d',
             listing_ok, len(discovered), valid_sections, len(found), len(metadata))
    return found, listing_ok > 0 or valid_sections > 0
