"""Execucao modular V3. Teste envia a ultima publicacao identificada por portal."""
import argparse,datetime,logging,re
from monitor.common import LOG,telegram_send,reconcile
from monitor.portais import ifsertaope,ifpb,compec
PORTALS={'ifsertaope':ifsertaope.collect,'ifpb':ifpb.collect,'compec':compec.collect}
def date_key(item):
    raw=item.get('date','')
    m=re.search(r'(\d{2})/(\d{2})/(\d{4})(?:[,\s]+(\d{2}):(\d{2}))?',raw)
    if m:
        day,month,year,hour,minute=m.groups()
        try:return datetime.datetime(int(year),int(month),int(day),int(hour or 0),int(minute or 0))
        except ValueError:pass
    # COMPEC sem data estruturada: selecao e por ordem de listagem, NAO por data comprovada
    return datetime.datetime.min

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['test-latest','monitor'],default='test-latest')
    parser.add_argument('--portal',choices=['all',*PORTALS],default='all')
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    names=list(PORTALS) if args.portal=='all' else [args.portal]
    errors=[]
    for name in names:
        LOG.info('Consultando %s (%s)',name,args.mode)
        try:
            found,valid=PORTALS[name]()
            if not valid or not found:
                LOG.warning('%s: sem publicacoes verificaveis nesta execucao',name)
                if args.mode=='test-latest':errors.append(name)
                continue
            if args.mode=='test-latest':
                latest=max(found.values(),key=date_key) if name!='compec' else next(iter(found.values()))
                if name=='compec':LOG.warning('COMPEC: sem data estruturada; enviando primeiro item relevante da listagem, nao ultima data confirmada')
                telegram_send(latest,testing=True)
                LOG.info('%s: mensagem de teste enviada ao Telegram',name)
            else:reconcile(name,found,valid)
        except Exception:
            LOG.exception('%s: falha isolada',name);errors.append(name)
    if errors:
        LOG.error('Portais com falha: %s', ', '.join(errors))
        if args.mode=='test-latest':raise SystemExit(1)
if __name__=='__main__':main()
