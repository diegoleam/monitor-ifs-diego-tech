"""Monitor IFs - Diego Tech. Coleta pública, comparação semântica e alertas Telegram."""
import os, re, json, time, hashlib, logging, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'state.json'
HEADERS = {'User-Agent': 'MonitorIFs-DiegoTech/2.0 (monitoramento publico; contato via repositorio GitHub)'}
SESSION = requests.Session(); SESSION.headers.update(HEADERS)
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
KEYWORDS = ('edital', 'concurso', 'selec', 'processo', 'resultado', 'retifica', 'convoca', 'inscri', 'homologa', 'noticia', 'notícia', 'bolsa', 'chamada', 'publica', 'publicaç', 'campus', 'campi', 'comunicado', 'recurso', 'classifica', 'cronograma', 'anexo', 'pdf')
EXCLUDE = ('login', 'logout', 'javascript:', 'mailto:', 'facebook.', 'instagram.', 'youtube.', 'whatsapp.', 'twitter.', 'x.com/', '/wp-admin/', '#')
log = logging.getLogger('monitor')

def normalize(s):
 s = unicodedata.normalize('NFKC', s or '')
 return re.sub(r'\s+', ' ', s).strip()

def canonical(url):
 u = urldefrag(url)[0]
 p = urlparse(u)
 return p._replace(query='', path=p.path.rstrip('/') or '/').geturl()

def get(url):
 for attempt in range(3):
  try:
   r = SESSION.get(url, timeout=TIMEOUT)
   r.raise_for_status()
   return r
  except requests.RequestException as exc:
   if attempt == 2: log.warning('Falha em %s: %s', url, exc)
   else: time.sleep(2 * (attempt+1))
 return None

def allowed(url, source):
 host = urlparse(url).hostname or ''
 return (host.endswith('ifsertaope.edu.br') if source == 'IFSertaoPE' else host.endswith('ifpb.edu.br'))

def relevant(text, url):
 value = (text + ' ' + url).lower()
 return any(k in value for k in KEYWORDS)

def parse_html(url, source):
 resp = get(url)
 if resp is None: return None
 if 'html' not in resp.headers.get('Content-Type', '').lower() and not resp.text.lstrip().startswith('<'): return None
 soup = BeautifulSoup(resp.content, 'html.parser')
 for el in soup(['script', 'style', 'noscript', 'svg', 'form', 'footer', 'nav', 'header']): el.decompose()
 main = soup.select_one('main, article, #content, .content, #portal-column-content, .portaltype-folder, .entry-content') or soup.body or soup
 text = normalize(main.get_text(' ', strip=True))[:70000]
 links = {}
 for a in main.find_all('a', href=True):
  href = canonical(urljoin(url, a['href']))
  if not href.startswith('http') or not allowed(href, source): continue
  if any(x in href.lower() for x in EXCLUDE): continue
  title = normalize(a.get_text(' ', strip=True) or a.get('title') or href.rsplit('/', 1)[-1])
  links[href] = title[:260]
 # fingerprint textual without menus; avoids page markup noise
 digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
 return {'text': text, 'hash': digest, 'links': links, 'title': normalize((soup.title.get_text(' ', strip=True) if soup.title else url))[:240]}

def file_hash(url):
 try:
  with SESSION.get(url, timeout=TIMEOUT, stream=True) as r:
   r.raise_for_status()
   size = int(r.headers.get('Content-Length', 0))
   if size > PDF_MAX_BYTES: return None
   h = hashlib.sha256(); count = 0
   for chunk in r.iter_content(65536):
    count += len(chunk)
    if count > PDF_MAX_BYTES: return None
    h.update(chunk)
   return h.hexdigest()
 except requests.RequestException as exc:
  log.warning('PDF indisponivel %s: %s', url, exc); return None

def notify(message):
 token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
 chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
 if not token or not chat:
  log.warning('Telegram nao configurado; alerta pendente, nao marcado como entregue.'); return False
 try:
  r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat, 'text': message[:3900], 'disable_web_page_preview': True}, timeout=20)
  r.raise_for_status()
  if not r.json().get('ok'): return False
  return True
 except (requests.RequestException, ValueError) as exc:
  log.warning('Erro Telegram: %s', exc); return False

def load():
 if not DB.exists(): return {'initialized': False, 'pages': {}, 'pdfs': {}, 'sent': []}
 try:
  data = json.loads(DB.read_text(encoding='utf-8'))
  return {'initialized': data.get('initialized', False), 'pages': data.get('pages', {}), 'pdfs': data.get('pdfs', {}), 'sent': data.get('sent', [])}
 except (OSError, ValueError) as exc:
  raise RuntimeError(f'Historico invalido: {exc}; nao recriar baseline automaticamente')

def save(db):
 DB.parent.mkdir(parents=True, exist_ok=True)
 temp = DB.with_suffix('.tmp'); temp.write_text(json.dumps(db, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8'); temp.replace(DB)

def main():
 logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
 db = load(); baseline = not db['initialized']
 seen = set(db['sent']); events = []; pdf_budget = MAX_PDFS
 pages = db['pages']; pdfs = db['pdfs']
 for source, roots in SOURCES.items():
  queue = [(u, 0) for u in roots]; visited = set(); details = 0
  while queue and len(visited) < MAX_PAGES + MAX_DETAILS:
   url, depth = queue.pop(0); url = canonical(url)
   if url in visited or not allowed(url, source): continue
   if depth > 0 and details >= MAX_DETAILS: continue
   visited.add(url)
   page = parse_html(url, source)
   if page is None: continue
   if depth > 0: details += 1
   old = pages.get(url)
   # Pages have new/changed relevant links; content-only change only on detail pages
   newlinks = [u for u in page['links'] if not old or u not in old.get('links', [])]
   changed = old is not None and old['hash'] != page['hash']
   if old is not None and changed and depth > 0 and relevant(page['title'], url):
    events.append((source, 'Conteudo da pagina alterado', page['title'], url, page['hash']))
   if old is not None:
    for link in newlinks:
     if relevant(page['links'][link], link):
      events.append((source, 'Novo link ou documento', page['links'][link], link, link))
   pages[url] = {'hash': page['hash'], 'links': list(page['links']), 'title': page['title'], 'checked_at': datetime.now(timezone.utc).isoformat()}
   # New candidates and existing known details: every run, within budgets
   candidates = [(u, t) for u, t in page['links'].items() if relevant(t, u)]
   for link, title in candidates:
    if link.lower().split('?')[0].endswith('.pdf'):
     if pdf_budget > 0 and (link not in pdfs or link in (old or {}).get('links', [])):
      pdf_budget -= 1
      digest = file_hash(link)
      if digest:
       if link in pdfs and pdfs[link] != digest:
        events.append((source, 'PDF alterado', title, link, digest))
       pdfs[link] = digest
    elif depth < 2 and link not in visited and len(queue) < 600:
     queue.append((link, depth+1))
   # Discover listing pagination and campus/editais paths, constrained to source
   if depth == 0:
    for link, title in page['links'].items():
     if ('editais' in link.lower() or 'concursos' in link.lower() or 'noticias' in link.lower() or 'notícias' in link.lower() or 'page=' in link.lower()) and link not in visited:
      queue.insert(0, (link, 1))
  log.info('%s: %d paginas verificadas', source, len(visited))
 # Do not mark alerts sent unless Telegram confirms success.
 if not baseline:
  for source, kind, title, url, digest in events:
   key = hashlib.sha256(f'{source}|{kind}|{url}|{digest}'.encode()).hexdigest()
   if key in seen: continue
   message = f'🚨 MONITOR IFs — {source}\n\n📌 {kind}\n📄 {title[:260]}\n🔗 {url}\n\nDesenvolvido por Diego Tech 🚀'
   if notify(message):
    seen.add(key); log.info('Alerta enviado: %s', title)
   else: log.warning('Alerta nao entregue: %s', title)
 else: log.info('Primeira execucao: baseline criado sem notificacoes antigas.')
 db['sent'] = list(seen)[-20000:]; db['initialized'] = True
 save(db)
 log.info('Finalizado. Eventos detectados: %d. Historico salvo.', len(events))

if __name__ == '__main__': main()
