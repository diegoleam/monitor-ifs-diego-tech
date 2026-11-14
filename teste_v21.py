"""Testes isolados da v2.1: nao acessa portais nem envia Telegram."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import monitor.main as monitor


def run():
    assert monitor.canonical('https://concursos.ifpb.edu.br/?page=2') == 'https://concursos.ifpb.edu.br/?page=2'
    assert monitor.canonical('https://concursos.ifpb.edu.br/?utm_source=x') == 'https://concursos.ifpb.edu.br/'
    print('OK: paginacao preservada')

    url = 'https://concursos.ifpb.edu.br/'
    pag2 = url + '?page=2'
    edital = 'https://concursos.ifpb.edu.br/editais/teste-novo'
    estado = {'initialized': True, 'pages': {
        url: {'hash': 'antigo', 'links': [pag2], 'title': 'COMPEC'},
        pag2: {'hash': 'antigo2', 'links': [], 'title': 'COMPEC pagina 2'},
    }, 'pdfs': {}, 'sent': []}

    def pagina(link, source):
        if link == url:
            return {'hash': 'antigo', 'links': {pag2: 'Pagina 2'}, 'title': 'COMPEC'}
        if link == pag2:
            return {'hash': 'novo2', 'links': {edital: 'Edital novo de teste'}, 'title': 'COMPEC pagina 2'}
        if link == edital:
            return {'hash': 'detalhe', 'links': {}, 'title': 'Edital novo de teste'}
        return None

    with tempfile.TemporaryDirectory() as pasta:
        db = Path(pasta) / 'state.json'
        db.write_text(json.dumps(estado), encoding='utf-8')
        entrega = {'ok': False}
        with patch.object(monitor, 'DB', db), \
             patch.object(monitor, 'SOURCES', {'COMPEC IFPB': [url]}), \
             patch.object(monitor, 'MAX_PAGES', 2), \
             patch.object(monitor, 'MAX_DETAILS', 5), \
             patch.object(monitor, 'parse_html', side_effect=pagina), \
             patch.object(monitor, 'notify', side_effect=lambda message: entrega['ok']) as aviso:
            monitor.main()
            data = json.loads(db.read_text(encoding='utf-8'))
            assert len(data['pending']) == 2, data['pending']
            assert len(data['sent']) == 0
            print('OK: falha do Telegram mantem alerta pendente')
            entrega['ok'] = True
            monitor.main()
            data = json.loads(db.read_text(encoding='utf-8'))
            assert not data['pending']
            assert len(data['sent']) == 2
            assert aviso.call_count == 4
            print('OK: reenvio bem-sucedido e sem duplicacao')
    print('TODOS OS TESTES ISOLADOS PASSARAM')


if __name__ == '__main__':
    run()
