"""COMPEC IFPB v3.6: acompanha novos processos e inscricoes exclusivas.

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


def extract(soup, url, process_link, title):
    """Apenas destinos exclusivos da COMPEC; paginas do IFPB ficam com o coletor IFPB."""
    found = {}
    scope = soup.select_one('main, #content, .content, article') or soup
    for row in scope.select('tr'):
        cells = row.find_all('td', recursive=False)
        for a in row.select('a[href]'):
            raw = (a.get('href') or '').strip()
            if not raw or raw.lower().startswith(('#', 'javascript:', 'mailto:')):
                continue
            link = canonical(urljoin(url, raw))
            parsed = urlparse(link)
            host = (parsed.hostname or '').lower()
            if not official(link) or any(x in parsed.path.lower() for x in SKIP):
                continue
            # O portal IFPB ja acompanha seus editais e documentos.
            if host in ('ifpb.edu.br', 'www.ifpb.edu.br'):
                continue
            if host == 'concursos.ifpb.edu.br':
                # Links para abas, processo ou paginacao nao sao novas oportunidades.
                if PAT.search(parsed.path):
                    continue
                if not (EXT.search(link) or DOWNLOAD.search(parsed.path)):
                    continue
            # A COMPEC usa links para inscricoes no Portal do Estudante.
            if host != 'estudante.ifpb.edu.br' and host != 'concursos.ifpb.edu.br':
                continue
            action = clean(a.get_text(' ', strip=True))
            if action.casefold() not in ('visitar', 'download', 'baixar', 'abrir', 'acessar', 'visualizar') and not DOC_WORDS.search(action):
                continue
            parts = [clean(td.get_text(' ', strip=True)) for td in cells]
            parts = [v for v in parts if v and v.casefold() not in ('visitar', 'download', 'baixar', 'abrir', 'acessar', 'visualizar')]
            label = max(parts, key=len) if parts else action
            context = clean(row.get_text(' ', strip=True))
            match = DATE.search(context)
            key = identifier('compec-ref', process_link, link)
            found[key] = dict(portal='COMPEC IFPB', kind='Inscrição ou referência exclusiva COMPEC',
                              edital=title, doc=label[:450] or title,
                              date=match.group(0) if match else '', link=link, origin=ROOT)
    return found


def process_item(origin, title):
    return dict(portal='COMPEC IFPB', kind='Novo processo seletivo',
                edital=title, doc='Processo seletivo disponível na COMPEC',
                date='', link=origin, origin=ROOT)

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
        found[identifier('compec-processo', uid)] = process_item(origin, title)
        for suffix in (f'editais/concurso/{uid}/editais/',
                       f'processos_seletivos/concurso/{uid}/documentos/'):
            section = urljoin(ROOT, suffix)
            sub = fetch(section)
            if sub is None:
                continue
            valid_sections += 1
            found.update(extract(sub, section, origin, title))
    LOG.info('COMPEC: listagens validas=%d processos descobertos=%d secoes validas=%d oportunidades=%d',
             listing_ok, len(discovered), valid_sections, len(found))
    return found, listing_ok > 0 or valid_sections > 0
