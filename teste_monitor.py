"""Teste isolado da lógica de identificação de eventos do Monitor IFs."""
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import monitor.main as monitor


def identificador(source, kind, url, digest):
    return hashlib.sha256(
        f"{source}|{kind}|{url}|{digest}".encode()
    ).hexdigest()


def executar_teste():
    with tempfile.TemporaryDirectory() as pasta:
        banco_teste = Path(pasta) / "state.json"

        url_portal = "https://www.ifpb.edu.br/editais"
        url_edital = "https://www.ifpb.edu.br/editais/edital-teste-diego-tech"
        titulo = "Edital ficticio de teste - Diego Tech"

        pagina = {
            "text": "Editais IFPB",
            "hash": "hash-pagina-teste",
            "links": {url_edital: titulo},
            "title": "Editais IFPB",
        }

        monitor.save_original = monitor.save
        monitor.DB = banco_teste
        monitor.SOURCES = {"IFPB": [url_portal]}
        monitor.MAX_PAGES = 1
        monitor.MAX_DETAILS = 0

        notificacoes = []

        def pagina_simulada(url, source):
            if url == url_portal:
                return pagina.copy()
            return None

        def telegram_simulado(mensagem):
            notificacoes.append(mensagem)
            return True

        with patch.object(monitor, "parse_html", side_effect=pagina_simulada), \
             patch.object(monitor, "notify", side_effect=telegram_simulado):

            monitor.save({
                "initialized": True,
                "pages": {
                    url_portal: {
                        "hash": "hash-anterior",
                        "links": [],
                        "title": "Editais IFPB",
                    }
                },
                "pdfs": {},
                "sent": [],
            })

            monitor.main()
            assert len(notificacoes) == 1, "Falhou: edital novo nao detectado."
            print("PASSOU: edital novo identificado.")

            monitor.main()
            assert len(notificacoes) == 1, "Falhou: notificacao duplicada."
            print("PASSOU: nenhuma notificacao duplicada.")

            pagina["links"] = {
                url_edital: titulo,
                "https://www.ifpb.edu.br/editais/retificacao-teste-diego-tech":
                    "Retificacao do edital ficticio - Diego Tech",
            }
            pagina["hash"] = "hash-pagina-alterada"

            monitor.main()
            assert len(notificacoes) == 2, "Falhou: retificacao nao detectada."
            print("PASSOU: nova retificacao identificada.")

        print("\nTESTE CONCLUIDO COM SUCESSO!")
        print("Nenhuma mensagem real foi enviada ao Telegram.")
        print("O historico original nao foi alterado.")


if __name__ == "__main__":
    executar_teste()
