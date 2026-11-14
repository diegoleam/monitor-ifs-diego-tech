"""IFPB: coleta tabela de arquivos de editais Plone e descobre paginas de editais."""
import os,re
from urllib.parse import urljoin,urlparse
from monitor.common import fetch,clean,canonical,identifier,LOG
ROOTS=['https://www.ifpb.edu.br/concursopublico/outros-editais/vigentes', 'https://www.ifpb.edu.br/editais']
EXAMPLE='https://www.ifpb.edu.br/concursopublico/outros-editais/vigentes/edital-no-161-2026-selecao-de-professor-formador-sape'
def is_edital(url):
    p=urlparse(url)
    return (p.hostname or '').endswith('ifpb.edu.br') and bool(re.search(r'/edital(?:-|_|\b)',p.path,re.I)) and not p.path.lower().endswith(('.pdf','.doc','.docx'))
def discover(soup,base):
    out={}
    for a in soup.select('a[href]'):
        url=canonical(urljoin(base,a['href']));title=clean(a.get_text(' ',strip=True))
        if is_edital(url) and (re.search(r'\bedital\b',title,re.I) or re.search(r'/edital-n',url,re.I)):
            out[url]=title or url.rsplit('/',1)[-1]
    return out

def extract(soup,url,title):
    table=soup.select_one('table.edital-items-table')
    if table is None:return None
    found={}
    for row in table.select('tbody.edital-items-body tr.edital-item-row, tbody tr.edital-item-row'):
        a=row.select_one('td.title a[href]')
        if a is None:continue
        link=canonical(urljoin(url,a['href']))
        if not (urlparse(link).hostname or '').endswith('ifpb.edu.br'):continue
        label=clean(a.get_text(' ',strip=True));description=clean((row.select_one('td.description') or row).get_text(' ',strip=True))
        t=row.select_one('td.date time');date=clean(t.get_text(' ',strip=True)) if t else clean((row.select_one('td.date') or row).get_text(' ',strip=True))
        key=identifier(url,link)
        found[key]=dict(portal='IFPB',kind='Documento publicado',edital=title,doc=label,date=date,description=description,link=link,origin=url)
    return found

def collect():
    candidates={EXAMPLE:'Edital nº 161/2026 – Seleção de Professor-Formador (Sapé)'}
    valid_listing=0
    for root in ROOTS:
        soup=fetch(root)
        if soup is None:continue
        valid_listing+=1;candidates.update(discover(soup,root))
    limit=max(1,min(120,int(os.getenv('IFPB_MAX_DETAILS','35'))))
    found={};valid_details=0
    for url,title in list(candidates.items())[:limit]:
        soup=fetch(url)
        if soup is None:continue
        docs=extract(soup,url,title)
        if docs is None:continue
        valid_details+=1;found.update(docs)
    LOG.info('IFPB: listagens=%d paginas de edital validas=%d documentos=%d',valid_listing,valid_details,len(found))
    return found,valid_details>0
