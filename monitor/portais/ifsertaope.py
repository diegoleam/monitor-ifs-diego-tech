"""IFSertaoPE: listagem /editais/ e documentos em table.edital__table."""
import os,re
from urllib.parse import urljoin,urlparse
from monitor.common import fetch,clean,canonical,identifier,LOG
ROOT='https://ifsertaope.edu.br/editais/'
def discover(soup):
    found={}
    for a in soup.select('a[href]'):
        url=canonical(urljoin(ROOT,a['href']));p=urlparse(url)
        if p.hostname=='ifsertaope.edu.br' and re.fullmatch(r'/editais/edital-[^/]+',p.path,re.I):
            found[url]=clean(a.get_text(' ',strip=True)) or p.path.rsplit('/',1)[-1]
    return found

def extract(soup,url,title):
    table=soup.select_one('table.edital__table')
    if table is None:return None
    found={}
    for tr in table.select('tbody tr'):
        cells=tr.find_all('td',recursive=False)
        if len(cells)<3:continue
        a=cells[1].select_one('a[href]')
        if not a:continue
        href=canonical(urljoin(url,a['href']))
        if urlparse(href).hostname!='ifsertaope.edu.br':continue
        label=clean(a.get_text(' ',strip=True));date=clean(cells[0].get_text(' ',strip=True));group=clean(cells[2].get_text(' ',strip=True))
        key=identifier(url,href)
        found[key]=dict(portal='IFSertãoPE',kind=group or 'Publicação',edital=title,doc=label,date=date,link=href,origin=url)
    return found

def collect():
    soup=fetch(ROOT)
    if soup is None:return {},False
    details=discover(soup)
    if not details:return {},False
    limit=max(1,min(100,int(os.getenv('IFS_MAX_DETAILS','30'))))
    found={};valid=0
    for url,title in list(details.items())[:limit]:
        page=fetch(url)
        if page is None:continue
        docs=extract(page,url,title)
        if docs is None:continue
        valid+=1;found.update(docs)
    LOG.info('IFSertaoPE: editais descobertos=%d paginas validas=%d documentos=%d',len(details),valid,len(found))
    return found,valid>0
