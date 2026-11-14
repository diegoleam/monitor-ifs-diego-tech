"""Diagnóstico somente-leitura de fontes públicas do IFSertãoPE."""
import requests
from urllib.parse import urlparse

URLS = {
    'Pagina de editais': 'https://ifsertaope.edu.br/editais/',
    'Pagina inicial': 'https://ifsertaope.edu.br/',
    'PDF edital 152': 'https://ifsertaope.edu.br/wp-content/uploads/2026/10/PDF_152_Edital-Chamada-Supera_Equipe-Tecnica_2026.pdf',
    'PDF resultado 152': 'https://ifsertaope.edu.br/wp-content/uploads/2026/11/Resultado-Preliminar_Edital_152_2026.pdf',
    'WordPress API raiz': 'https://ifsertaope.edu.br/wp-json/',
    'WordPress API tipos': 'https://ifsertaope.edu.br/wp-json/wp/v2/types',
}

HEADERS = {'User-Agent': 'MonitorIFs-DiegoTech/diagnostico (consulta publica)', 'Accept': 'text/html,application/json,application/pdf;q=0.9,*/*;q=0.5'}

def main():
    for nome, url in URLS.items():
        print(f'\n=== {nome} ===', flush=True)
        print(f'URL: {url}', flush=True)
        try:
            # stream evita baixar PDFs inteiros e minimiza carga no servidor
            with requests.get(url, headers=HEADERS, timeout=20, stream=True, allow_redirects=True) as resposta:
                print(f'HTTP: {resposta.status_code}', flush=True)
                print(f'URL final: {resposta.url}', flush=True)
                tipo = resposta.headers.get('Content-Type', 'nao informado')
                print(f'Content-Type: {tipo}', flush=True)
                print(f'Content-Length: {resposta.headers.get("Content-Length", "nao informado")}', flush=True)
                trecho = next(resposta.iter_content(chunk_size=4096), b'')
                assinatura_pdf = trecho.startswith(b'%PDF-')
                texto = trecho.decode('utf-8', errors='replace').lower()
                captcha = any(x in texto for x in ('radware captcha', 'captcha page', 'access denied', 'verify you are human'))
                print(f'Assinatura PDF: {"SIM" if assinatura_pdf else "NAO"}', flush=True)
                print(f'Indicador de bloqueio no inicio da resposta: {"SIM" if captcha else "NAO"}', flush=True)
                if 'json' in tipo.lower():
                    print('API: resposta JSON identificada (sem coletar dados pessoais)', flush=True)
                elif 'html' in tipo.lower() and not captcha:
                    print('HTML: resposta recebida; validar conteudo em etapa posterior', flush=True)
        except requests.RequestException as exc:
            print(f'ERRO: {type(exc).__name__}: {exc}', flush=True)
    print('\nDiagnostico concluido. Nenhum arquivo de estado foi alterado.', flush=True)

if __name__ == '__main__':
    main()
