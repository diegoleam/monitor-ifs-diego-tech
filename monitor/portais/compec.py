"""COMPEC: acompanha processos UUID e as abas oficiais de editais/publicacoes."""
import os,re
from urllib.parse import urljoin,urlparse
from monitor.common import fetch,clean,canonical,identifier,LOG
ROOT='https://concursos.ifpb.edu.br/'
UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
PAT=re.compile(r'/((?:processos_seletivos|editais)/concurso)/('+UUID+r')',re.I)
START=[ROOT, urljoin(ROOT,'processos_seletivos/')]
SKIP=('login','logout','faq','cadastro','javascript:','mailto:')

def processes(soup,base):
    found={}
    for a in soup.select('a[href]'):
        u=canonical(urljoin(base,a['href']));m=PAT.search(urlparse(u).path)
        if m and (urlparse(u).hostname or '').lower()=='concursos.ifpb.edu.br':
            uid=m.group(2).lower();found[uid]=urljoin(ROOT,'processos_seletivos/concurso/'+uid+'/')
    return found

def extract(soup,url,process_url,process_name):
    found={}
    # Somente areas de publicacao; menus, rodapes e navegacao nao viram documentos.
    main=soup.select_one('main, #content, .content, article') or soup
    for a in main.select('a[href]'):
        link=canonical(urljoin(url,a['href']));path=urlparse(link).path.lower()
        label=clean(a.get_text(' ',strip=True) or a.get('title') or '')
        if not label or any(x in path for x in SKIP):continue
        if link==canonical(url) or link==canonical(process_url):continue
        if PAT.search(path) and not (path.endswith('.pdf') or '/download/' in path):continue
        # Anexos e downloads oficiais; links de navegacao sao excluidos.
        is_doc=bool(re.search(r'\.(pdf|docx?|xlsx?|odt|ods)(?:$|\?)',link,re.I) or '/download/' in path or '/arquivo/' in path)
        if not is_doc:continue
        host=(urlparse(link).hostname or '').lower()
        if not (host.endswith('ifpb.edu.br')):continue
        container=a.find_parent(['tr','li','div'])
        context=clean(container.get_text(' ',strip=True)) if container else label
        date_match=re.search(r'\b\d{2}/\d{2}/\d{4}(?:[, ]+\d{2}:\d{2})?',context)
        key=identifier(process_url,link)
        found[key]=dict(portal='COMPEC IFPB',kind='Documento publicado',edital=process_name,doc=label,date=date_match.group(0) if date_match else '',link=link,origin=process_url)
    return found

def collect():
    discovered={};listing_ok=0
    for url in START:
        soup=fetch(url)
        if soup is None:continue
        listing_ok+=1;discovered.update(processes(soup,url))
    # Processo de referencia conhecido, configuravel; nao substitui descoberta automatica.
    seeds=os.getenv('COMPEC_PROCESS_URLS','https://concursos.ifpb.edu.br/processos_seletivos/concurso/beab9b5a-0554-4ee8-8f8e-6e959520deb9/').split(',')
    for raw in seeds:
        m=PAT.search(urlparse(raw.strip()).path)
        if m:discovered[m.group(2).lower()]=urljoin(ROOT,'processos_seletivos/concurso/'+m.group(2).lower()+'/')
    limit=max(1,min(60,int(os.getenv('COMPEC_MAX_PROCESSES','12'))))
    found={};valid=0
    for uid,origin in list(discovered.items())[:limit]:
        page=fetch(origin)
        if page is None:continue
        title=clean((page.select_one('h1,h2') or page.title).get_text(' ',strip=True)) if (page.select_one('h1,h2') or page.title) else 'Processo '+uid
        for suffix in ('editais/concurso/'+uid+'/editais/','processos_seletivos/concurso/'+uid+'/documentos/'):
            url=urljoin(ROOT,suffix);sub=fetch(url)
            if sub is None:continue
            valid+=1;found.update(extract(sub,url,origin,title))
    LOG.info('COMPEC: listagens validas=%d processos descobertos=%d secoes validas=%d documentos=%d',listing_ok,len(discovered),valid,len(found))
    return found,valid>0
