"""COMPEC: coletor proprio; usa links de processos e publicacoes, nao tabela do IFPB."""
import os,re
from urllib.parse import urljoin,urlparse
from monitor.common import fetch,clean,canonical,identifier,LOG
ROOT='https://concursos.ifpb.edu.br/'
KEYWORDS=('edital','processo seletivo','concurso','resultado','homologa','retifica','convoca','recurso','inscri')
JUNK=('login','logout','faq','entrar','próximo','proximo','anterior','página','pagina','início','inicio','cadastro')
def collect():
    soup=fetch(ROOT)
    if soup is None:return {},False
    main=soup.select_one('main, #content, .content, article') or soup
    found={}
    for a in main.select('a[href]'):
        label=clean(a.get_text(' ',strip=True));link=canonical(urljoin(ROOT,a['href']))
        host=(urlparse(link).hostname or '').lower()
        if not host.endswith('ifpb.edu.br') or len(label)<12:continue
        low=label.lower();path=urlparse(link).path.lower()
        if low in JUNK or any(x in path for x in ('login','logout','faq')):continue
        if not any(k in low for k in KEYWORDS):continue
        if re.search(r'\b(19|20)\d{2}\b',low+' '+path) is None:continue
        key=identifier(link)
        found[key]=dict(portal='COMPEC IFPB',kind='Publicação identificada',edital=label[:200],doc=label[:200],date='',link=link,origin=ROOT)
    LOG.info('COMPEC: links relevantes encontrados=%d',len(found))
    return found,bool(found)
