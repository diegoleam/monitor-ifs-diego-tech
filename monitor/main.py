"""Monitor IFs - Diego Tech. Monitoramento publico e alertas Telegram."""
import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'state.json'
HEADERS = {'User-Agent': 'MonitorIFs-DiegoTech/2.1 (monitoramento publico; contato via repositorio GitHub)'}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
TIMEOUT = 22
MAX_PAGES = int(os.getenv('MAX_PAGES_PER_SOURCE', '8'))
MAX_DETAILS = int(os.getenv('MAX_DETAILS_PER_RUN', '45'))
MAX_PDFS = int(os.getenv('MAX_PDFS_PER_RUN', '12'))
PDF_MAX_BYTES = 12 * 1024 * 1024
SOURCES = {
    'IFSertaoPE': ['https://ifsertaope.edu.br/editais/', 'https://ifsertaope.edu.br/'],
    'IFPB': ['https://www.ifpb.edu.br/editais', 'https://www.ifpb.edu.br/'],
    'COMPEC IFPB': ['https://concursos.ifpb.edu.br/'],
}
KEYWORDS = ('edital', 'concurso', 'selec', 'processo', 'resultado', 'retifica', 'convoca',
            'inscri', 'homologa', 'noticia', 'notícia', 'bolsa', 'chamada', 'publica',
            'publicaç', 'campus', 'campi', 'comunicado', 'recurso', 'classifica',
            'cronograma', 'anexo', 'pdf')
EXCLUDE = ('login', 'logout', 'javascript:', 'mailto:', 'facebook.', 'instagram.',
           'youtube.', 'whatsapp.', 'twitter.', 'x.com/', '/wp-admin/')
BLOCK_MARKERS = ('radware captcha', 'access denied', 'verify you are human',
                 'captcha challenge', 'attention required! | cloudflare')
log = logging.getLogger('monitor')


def normalize(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s or '')).strip()


def canonical(url):
    """Preserva apenas parametros de paginacao, evitando duplicatas de rastreamento."""
    p = urlparse(urldefrag(url)[0])
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                             if k.lower() in ('page', 'pagina', 'p') and v.isdigit()))
    return p._replace(query=query, path=p.path.rstrip('/') or '/').geturl()


def get(url):
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            if attempt == 2:
                log.warning('Falha em %s: %s', url, exc)
            else:
                time.sleep(2 * (attempt + 1))
    return None


def allowed(url, source):
    host = (urlparse(url).hostname or '').lower()
    domain = 'ifsertaope.edu.br' if source == 'IFSertaoPE' else 'ifpb.edu.br'
    return host == domain or host.endswith('.' + domain)


def relevant(text, url):
    value = (text + ' ' + url).lower()
    return any(k in value for k in KEYWORDS)


def parse_html(url, source):
    resp = get(url)
    if resp is None:
        return None
    if 'html' not in resp.headers.get('Content-Type', '').lower() and not resp.text.lstrip().startswith('<'):
        return None
    soup = BeautifulSoup(resp.content, 'html.parser')
    title = normalize(soup.title.get_text(' ', strip=True) if soup.title else url)[:240]
    body_preview = normalize(soup.get_text(' ', strip=True))[:3500].lower()
    if any(marker in (title + ' ' + body_preview).lower() for marker in BLOCK_MARKERS):
        log.warning('Pagina de bloqueio ignorada: %s (%s)', url, title)
        return None
    for el in soup(['script', 'style', 'noscript', 'svg', 'form', 'footer']):
        el.decompose()
    main = soup.select_one('main, article, #content-core, #parent-fieldname-text, #content, .content, #portal-column-content, .portaltype-folder, .entry-content') or soup.body or soup
    # O texto do conteudo e usado para detectar alteracoes; os links sao comparados separadamente.
    text = normalize(main.get_text(' ', strip=True))[:70000]
    links = {}
    for a in main.find_all('a', href=True):
        raw = a['href'].strip()
        if raw.startswith('#'):
            continue
        href = canonical(urljoin(url, raw))
        if urlparse(href).scheme not in ('http', 'https') or not allowed(href, source):
            continue
        if any(x in href.lower() for x in EXCLUDE):
            continue
        label = normalize(a.get_text(' ', strip=True) or a.get('title') or href.rsplit('/', 1)[-1])
        links[href] = label[:260]
    # Recupera paginacao mesmo quando o portal a coloca fora do conteudo principal.
    for a in soup.find_all('a', href=True):
        href = canonical(urljoin(url, a['href']))
        if 'page=' in href.lower() and allowed(href, source) and href not in links:
            links[href] = normalize(a.get_text(' ', strip=True) or 'Pagina')[:260]
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return {'text': text, 'hash': digest, 'links': links, 'title': title}


def file_hash(url):
    try:
        with SESSION.get(url, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            size = int(r.headers.get('Content-Length', 0))
            if size > PDF_MAX_BYTES:
                return None
            h = hashlib.sha256()
            count = 0
            for chunk in r.iter_content(65536):
                count += len(chunk)
                if count > PDF_MAX_BYTES:
                    return None
                h.update(chunk)
            return h.hexdigest()
    except (requests.RequestException, ValueError) as exc:
        log.warning('PDF indisponivel %s: %s', url, exc)
        return None


def notify(message):
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat:
        log.warning('Telegram nao configurado; alerta pendente.')
        return False
    try:
        r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                          json={'chat_id': chat, 'text': message[:3900],
                                'disable_web_page_preview': True}, timeout=20)
        r.raise_for_status()
        return bool(r.json().get('ok'))
    except (requests.RequestException, ValueError) as exc:
        log.warning('Erro Telegram: %s', exc)
        return False


def load():
    if not DB.exists():
        return {'initialized': False, 'pages': {}, 'pdfs': {}, 'sent': [], 'pending': []}
    try:
        data = json.loads(DB.read_text(encoding='utf-8'))
        return {'initialized': data.get('initialized', False), 'pages': data.get('pages', {}),
                'pdfs': data.get('pdfs', {}), 'sent': data.get('sent', []),
                'pending': data.get('pending', [])}
    except (OSError, ValueError) as exc:
        raise RuntimeError(f'Historico invalido: {exc}; nao recriar baseline automaticamente')


def save(db):
    DB.parent.mkdir(parents=True, exist_ok=True)
    temp = DB.with_suffix('.tmp')
    temp.write_text(json.dumps(db, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    temp.replace(DB)


def is_pdf(url):
    return urlparse(url).path.lower().endswith('.pdf')


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    db = load()
    baseline = not db['initialized']
    pages, pdfs = db['pages'], db['pdfs']
    sent_order = list(dict.fromkeys(db['sent']))
    sent = set(sent_order)
    pending = {item['key']: item for item in db['pending'] if item.get('key') and item.get('message')}
    events = []
    for source, roots in SOURCES.items():
        queue = deque((canonical(url), 0) for url in roots)
        visited = set()
        details = 0
        root_count = 0
        success = 0
        pdf_budget = MAX_PDFS  # Limite individual por instituicao
        pdf_checked = set()
        while queue:
            url, depth = queue.popleft()
            url = canonical(url)
            if url in visited or not allowed(url, source):
                continue
            if depth > 2 or (depth > 0 and details >= MAX_DETAILS):
                continue
            if depth == 0 and root_count >= MAX_PAGES:
                continue
            visited.add(url)
            if depth == 0:
                root_count += 1
            else:
                details += 1
            page = parse_html(url, source)
            if page is None:
                continue
            success += 1
            old = pages.get(url)
            newlinks = [link for link in page['links'] if old and link not in old.get('links', [])]
            changed = old is not None and old.get('hash') != page['hash']
            if changed and depth > 0 and relevant(page['title'], url):
                events.append((source, 'Conteudo da pagina alterado', page['title'], url, page['hash']))
            for link in newlinks:
                if relevant(page['links'][link], link):
                    events.append((source, 'Novo link ou documento', page['links'][link], link, link))
            pages[url] = {'hash': page['hash'], 'links': list(page['links']),
                          'title': page['title'], 'checked_at': datetime.now(timezone.utc).isoformat()}
            for link, label in page['links'].items():
                if is_pdf(link):
                    if link in pdf_checked or pdf_budget <= 0:
                        continue
                    pdf_checked.add(link)
                    pdf_budget -= 1
                    digest = file_hash(link)
                    if digest:
                        if link in pdfs and pdfs[link] != digest:
                            events.append((source, 'PDF alterado', label, link, digest))
                        elif link not in pdfs and old is not None:
                            events.append((source, 'Novo PDF identificado', label, link, digest))
                        pdfs[link] = digest
                elif depth < 2 and relevant(label, link) and link not in visited and len(queue) < 600:
                    queue.append((link, depth + 1))
            # Paginas de listagem e paginacao sao priorizadas, sem eliminar ?page=N.
            if depth == 0:
                priority = [(link, 1) for link in page['links']
                            if ('editais' in link.lower() or 'concursos' in link.lower()
                                or 'noticias' in link.lower() or 'page=' in link.lower())
                            and not is_pdf(link) and link not in visited]
                queue.extendleft(reversed(priority[:100]))
        log.info('%s: %d paginas lidas; %d URLs tentadas; %d PDFs verificados',
                 source, success, len(visited), len(pdf_checked))

    if baseline:
        log.info('Primeira execucao: baseline criado sem notificacoes antigas.')
    else:
        for source, kind, title, url, digest in events:
            key = hashlib.sha256(f'{source}|{kind}|{url}|{digest}'.encode()).hexdigest()
            if key in sent or key in pending:
                continue
            message = (f'🚨 MONITOR IFs — {source}\n\n📌 {kind}\n📄 {title[:260]}\n'
                       f'🔗 {url}\n\nDesenvolvido por Diego Tech 🚀')
            pending[key] = {'key': key, 'message': message}
    # Persistir a fila ANTES de tentar o Telegram evita perda de alertas.
    db['pending'] = list(pending.values())
    db['initialized'] = True
    save(db)
    for key, item in list(pending.items()):
        if notify(item['message']):
            sent.add(key)
            sent_order.append(key)
            del pending[key]
            db['pending'] = list(pending.values())
            db['sent'] = sent_order[-20000:]
            save(db)
            log.info('Alerta enviado: %s', key[:12])
        else:
            log.warning('Alerta pendente: %s', key[:12])
    db['sent'] = sent_order[-20000:]
    db['pending'] = list(pending.values())
    save(db)
    log.info('Finalizado. Eventos detectados: %d; alertas pendentes: %d.', len(events), len(pending))


if __name__ == '__main__':
    main()
