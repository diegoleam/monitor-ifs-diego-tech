
"""Execucao modular V3. Teste envia a ultima publicacao identificada por portal."""

import argparse
import datetime
import logging
import re

from monitor.common import LOG, telegram_send, reconcile
from monitor.portais import ifsertaope, ifpb, compec


PORTALS = {
    'ifsertaope': ifsertaope.collect,
    'ifpb': ifpb.collect,
    'compec': compec.collect,
}


def date_key(item):
    """Data utilizada pelo modo de teste do IFPB."""
    raw = item.get('date', '')

    m = re.search(
        r'(\d{2})/(\d{2})/(\d{4})(?:[,\s]+(\d{2}):(\d{2}))?',
        raw
    )

    if m:
        day, month, year, hour, minute = m.groups()

        try:
            return datetime.datetime(
                int(year),
                int(month),
                int(day),
                int(hour or 0),
                int(minute or 0)
            )
        except ValueError:
            pass

    # COMPEC sem data estruturada: selecao e por ordem
    # de listagem, NAO por data comprovada.
    return datetime.datetime.min


def ifsertaope_update_key(item):
    """
    Identifica a ultima atualizacao do edital do IFSertaoPE.

    A data e obtida do campo 'description', que contem:
    Ultima atualizacao: DD/MM/AAAA HH:MM

    Nao utiliza a data original de publicacao do edital.
    """
    description = item.get('description', '')

    m = re.search(
        r'Ultima atualizacao:\s*'
        r'(\d{2})/(\d{2})/(\d{4})\s+'
        r'(\d{2}):(\d{2})',
        description,
        re.IGNORECASE
    )

    if m:
        day, month, year, hour, minute = m.groups()

        try:
            return datetime.datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute)
            )
        except ValueError:
            pass

    return datetime.datetime.min


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--mode',
        choices=['test-latest', 'monitor'],
        default='test-latest'
    )

    parser.add_argument(
        '--portal',
        choices=['all', *PORTALS],
        default='all'
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s %(message)s'
    )

    names = list(PORTALS) if args.portal == 'all' else [args.portal]

    errors = []

    for name in names:
        LOG.info('Consultando %s (%s)', name, args.mode)

        try:
            found, valid = PORTALS[name]()

            if not valid or not found:
                LOG.warning(
                    '%s: sem publicacoes verificaveis nesta execucao',
                    name
                )

                if args.mode == 'test-latest':
                    errors.append(name)

                continue

            if args.mode == 'test-latest':

                # IFSertaoPE:
                # Seleciona o edital pela ultima atualizacao.
                if name == 'ifsertaope':
                    editais = [
                        item
                        for item in found.values()
                        if item.get('kind') == 'Novo edital'
                    ]

                    if not editais:
                        LOG.warning(
                            'IFSertaoPE: nenhum edital valido para teste'
                        )
                        errors.append(name)
                        continue

                    latest = max(
                        editais,
                        key=ifsertaope_update_key
                    )

                    LOG.info(
                        'IFSertaoPE: edital selecionado pelo campo '
                        'Ultima Atualizacao: %s',
                        latest.get('edital', '')
                    )

                # COMPEC:
                # Mantem a escolha pela ordem original da listagem.
                elif name == 'compec':
                    latest = next(iter(found.values()))

                    LOG.warning(
                        'COMPEC: sem data estruturada; enviando '
                        'primeiro item relevante da listagem, '
                        'nao ultima data confirmada'
                    )

                # IFPB:
                # Mantem exatamente a selecao anterior pela data.
                else:
                    latest = max(
                        found.values(),
                        key=date_key
                    )

                telegram_send(
                    latest,
                    testing=True
                )

                LOG.info(
                    '%s: mensagem de teste enviada ao Telegram',
                    name
                )

            else:
                # Monitoramento automatico:
                # Mantem a reconciliacao e o historico existentes.
                reconcile(name, found, valid)

        except Exception:
            LOG.exception(
                '%s: falha isolada',
                name
            )
            errors.append(name)

    if errors:
        raise SystemExit(
            'Falha nos portais: ' + ', '.join(errors)
        )


if __name__ == '__main__':
    main()
