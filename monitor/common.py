"""HTTP, estado e Telegram compartilhados; nenhum portal depende de outro."""
import html
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

LOG = logging.getLogger('monitor_ifs')
DATA = Path(__file__).resolve().parents[1] / 'data'
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'MonitorIFs-DiegoTech/3.0 (monitoramento publico; contato via repositorio)'
})
SIGNATURE = 'Desenvolvido por Diego Tech'


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def canonical(url):
    u = urldefrag(url)[0]
    p = urlparse(u)
    return p._replace(path=p.path.rstrip('/') or '/').geturl()


def identifier(*parts):
    return hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()


def fetch(url):
    try:
        r = SESSION.get(url, timeout=25, allow_redirects=True)
        r.raise_for_status()
        host = (urlparse(r.url).hostname or '').lower()
        if host.endswith('perfdrive.com') or 'radware captcha page' in r.text[:15000].lower():
            LOG.warning('Protecao do portal impediu leitura: %s', url)
            return None
        if 'html' not in r.headers.get('Content-Type', '').lower():
            return None
        return BeautifulSoup(r.content, 'html.parser')
    except requests.RequestException as e:
        LOG.warning('Falha de acesso a %s: %s', url, e)
        return None


def empty():
    return {'initialized': False, 'items': {}, 'pending': {}, 'sent': []}


def load(portal):
    path = DATA / f'{portal}.json'
    if not path.exists():
        return empty()
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('items'), dict):
        raise ValueError(f'Estado invalido: {path}')
    for k, v in empty().items():
        data.setdefault(k, v)
    return data


def save(portal, data):
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / f'{portal}.json'
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    tmp.replace(p)


def format_message(item, testing=False):
    e = lambda x: html.escape(clean(x), quote=False)
    portal = e(item.get('portal'))
    kind = e(item.get('kind', 'Nova publicação'))
    title = e(item.get('edital'))
    doc = e(item.get('doc'))
    date = e(item.get('date'))
    desc = e(item.get('description', ''))
    link = html.escape(item.get('link', ''), quote=True)
    origin = html.escape(item.get('origin', ''), quote=True)
    header = ('🧪 <b>TESTE — ÚLTIMA PUBLICAÇÃO IDENTIFICADA</b>\n'
              if testing else '🔔 <b>NOVA PUBLICAÇÃO IDENTIFICADA</b>\n')
    lines = [header, '📢 <b>MONITOR IFs | DIEGO TECH</b>',
             f'🏛 <b>{portal}</b>', f'📋 <b>{title[:450]}</b>',
             f'📄 <b>{doc[:450]}</b>', f'🏷 {kind[:150]}']
    if date:
        lines.append(f'📅 {date}')
    if desc and desc.lower() != doc.lower():
        lines.append(f'📝 {desc[:400]}')
    if link:
        lines.append(f'📎 <a href="{link}">Abrir documento</a>')
    if origin:
        lines.append(f'🌐 <a href="{origin}">Página oficial do edital</a>')
    lines.extend(['', f'💻 <i>{SIGNATURE}</i>'])
    return '\n'.join(lines)


def telegram_send(item, testing=False):
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat:
        raise RuntimeError('Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nos Secrets')
    response = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': chat, 'text': format_message(item, testing),
              'parse_mode': 'HTML', 'disable_web_page_preview': True},
        timeout=25,
    )
    response.raise_for_status()
    if not response.json().get('ok'):
        raise RuntimeError('Telegram nao confirmou o envio')


def _compec_process_for_reference(ref_key, ref_item, process_items):
    """Relaciona referencia ao processo pelo identificador v3.7, sem alterar chaves."""
    for process_key, process_item in process_items.items():
        process_link = process_item.get('link', '')
        ref_link = ref_item.get('link', '')
        if process_link and ref_link and identifier('compec-ref', process_link, ref_link) == ref_key:
            return process_key, process_item
    return None, None


def reconcile(portal, documents, valid, observed_origins=None):
    """Historico independente por portal; COMPEC agrupa processo e inscricao novos."""
    if not valid:
        LOG.warning('%s: coleta indisponivel; estado preservado', portal)
        return

    state = load(portal)
    known = state['items']
    pending = state['pending']
    origins = {v.get('origin') for v in known.values() if v.get('origin')}
    sent = set(state['sent'])
    initialized = bool(state['initialized'])
    is_compec = portal.lower() == 'compec'
    new = 0

    # Primeiro seleciona novos registros sem modificar os IDs persistidos.
    candidates = {}
    for key, item in documents.items():
        if initialized and key not in known and key not in pending and key not in sent:
            if is_compec or item.get('origin') in origins:
                candidates[key] = item
        known[key] = item

    if is_compec and candidates:
        # As chaves da v3.7 distinguem processos e referencias. Nao as recalcular.
        processes = {
            key: item for key, item in known.items()
            if key == identifier('compec-processo',
                                 (re.search(r'/concurso/([0-9a-f-]{36})', item.get('link', '')) or [None, ''])[1])
            and item.get('kind') == 'Novo processo seletivo'
        }
        new_processes = {key for key in candidates if key in processes}
        suppressed = 0
        for key, item in candidates.items():
            if item.get('kind') != 'Inscrição ou referência exclusiva COMPEC':
                continue
            process_key, process_item = _compec_process_for_reference(key, item, processes)
            if process_item is None:
                continue
            if process_key in new_processes:
                # Uma mensagem por processo novo. A referencia continua no historico.
                if process_key not in pending:
                    pending[process_key] = dict(candidates[process_key])
                notice = pending[process_key]
                if notice.get('link') == process_item.get('link'):
                    notice['link'] = item['link']
                    notice['origin'] = process_item['link']
                    notice['description'] = (notice.get('description', '') +
                                             ' | Link de inscrição disponível').strip(' |')
                suppressed += 1
                continue
            # Referencia adicionada posteriormente: avisar com link do processo.
            pending[key] = dict(item, origin=process_item['link'])
            new += 1
        for key, item in candidates.items():
            if item.get('kind') == 'Inscrição ou referência exclusiva COMPEC':
                if key in pending or _compec_process_for_reference(key, item, processes)[0] in new_processes:
                    continue
            if key not in pending:
                pending[key] = item
            new += 1
        if suppressed:
            LOG.info('COMPEC: %d referencias agrupadas aos processos novos', suppressed)
    else:
        for key, item in candidates.items():
            pending[key] = item
            new += 1

    if not documents and not initialized:
        LOG.warning('%s: sem dados para baseline', portal)
        return

    state['initialized'] = True
    save(portal, state)

    for key, item in list(pending.items()):
        if key in sent:
            pending.pop(key, None)
            save(portal, state)
            continue
        try:
            telegram_send(item)
        except (requests.RequestException, ValueError, RuntimeError) as e:
            LOG.warning('%s: alerta pendente %s: %s', portal, key[:10], e)
            continue
        state['sent'].append(key)
        sent.add(key)
        pending.pop(key, None)
        save(portal, state)

    LOG.info('%s: documentos lidos=%s novos=%s pendentes=%s',
             portal, len(documents), new, len(pending))
