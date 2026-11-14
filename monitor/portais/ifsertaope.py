"""IFSertaoPE: editais pela listagem; documentos individuais quando acessiveis.

Compativel com monitor.common e monitor.main v3. Nao altera outros portais.
"""
import os
import re
from urllib.parse import urljoin, urlparse
from monitor.common import fetch, clean, canonical, identifier, LOG

ROOT = 'https://ifsertaope.edu.br/editais/'
DETAIL = re.compile(r'/editais/edital-[^/]+/?$', re.I)
DATE = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')


def discover(soup):
    """Retorna {url: titulo}, mantendo compatibilidade com a versao anterior."""
    found = {}
    for a in soup.select('a[href]'):
        url = canonical(urljoin(ROOT, a['href']))
        p = urlparse(url)
        if p.hostname == 'ifsertaope.edu.br' and DETAIL.fullmatch(p.path):
            found[url] = clean(a.get_text(' ', strip=True)) or p.path.rsplit('/', 1)[-1]
    return found


def listing_items(soup):
    """Lê apenas dados visíveis nas linhas da listagem oficial."""
    found = {}
    # Tabela da listagem: Ultima atualizacao | Edital | Data do edital | Categorias | Status
    for table in soup.select('table'):
        headings = [clean(th.get_text(' ', strip=True)).casefold() for th in table.select('thead th')]
        is_listing = ('edital' in ' '.join(headings) and
                      ('categor' in ' '.join(headings) or 'status' in ' '.join(headings)))
        if not is_listing:
            continue
        for row in table.select('tbody tr'):
            cells = row.find_all('td', recursive=False)
            if len(cells) < 2:
                continue
            a = next((a for a in row.select('a[href]')
                      if urlparse(canonical(urljoin(ROOT, a['href']))).hostname == 'ifsertaope.edu.br'
                      and DETAIL.fullmatch(urlparse(canonical(urljoin(ROOT, a['href']))).path)), None)
            if a is None:
                continue
            url = canonical(urljoin(ROOT, a['href']))
            title = clean(a.get_text(' ', strip=True))
            if not title:
                continue
            values = [clean(td.get_text(' ', strip=True)) for td in cells]
            # A estrutura oficial observada tem cinco colunas. Evita atribuir
            # campos errados se o portal alterar o layout.
            update = values[0] if len(values) >= 5 else ''
            published = values[2] if len(values) >= 5 else ''
            category = values[3] if len(values) >= 5 else ''
            status = values[4] if len(values) >= 5 else ''
            details = []
            if update:
                details.append('Ultima atualizacao: ' + update)
            if category:
                details.append('Categoria: ' + category)
            if status:
                details.append('Situacao: ' + status)
            key = identifier('ifs-edital', url)
            found[key] = dict(portal='IFSertãoPE', kind='Novo edital',
                              edital=title, doc='Edital publicado no IFSertãoPE',
                              date=published if DATE.search(published) else '',
                              description=' | '.join(details), link=url, origin=url)
    return found


def extract(soup, url, title):
    """Preserva a coleta de documentos da versao anterior."""
    table = soup.select_one('table.edital__table')
    if table is None:
        return None
    found = {}
    for tr in table.select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) < 3:
            continue
        a = cells[1].select_one('a[href]')
        if not a:
            continue
        href = canonical(urljoin(url, a['href']))
        if urlparse(href).hostname != 'ifsertaope.edu.br':
            continue
        label = clean(a.get_text(' ', strip=True))
        date = clean(cells[0].get_text(' ', strip=True))
        group = clean(cells[2].get_text(' ', strip=True))
        key = identifier(url, href)
        found[key] = dict(portal='IFSertãoPE', kind=group or 'Publicação',
                          edital=title, doc=label, date=date, link=href, origin=url)
    return found


def collect():
    soup = fetch(ROOT)
    if soup is None:
        return {}, False
    details = discover(soup)
    listed = listing_items(soup)
    if not details and not listed:
        LOG.warning('IFSertaoPE: listagem sem editais verificaveis')
        return {}, False
    limit = max(0, min(100, int(os.getenv('IFS_MAX_DETAILS', '0'))))
    found = dict(listed)
    valid = 0
    for url, title in list(details.items())[:limit]:
        page = fetch(url)
        if page is None:
            continue
        docs = extract(page, url, title)
        if docs is None:
            continue
        valid += 1
        found.update(docs)
    LOG.info('IFSertaoPE: editais descobertos=%d listagem=%d paginas validas=%d documentos=%d registros=%d',
             len(details), len(listed), valid, len(found)-len(listed), len(found))
    # Somente a tabela confirmada ou paginas individuais validas autorizam baseline.
    return found, bool(listed) or valid > 0
