import requests
from bs4 import BeautifulSoup

portais = {
    "IFSertaoPE": "https://ifsertaope.edu.br/editais/",
    "IFPB": "https://www.ifpb.edu.br/editais",
    "COMPEC": "https://concursos.ifpb.edu.br/",
}

for nome, url in portais.items():
    print(f"\n--- {nome} ---")
    try:
        resposta = requests.get(
            url,
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        sopa = BeautifulSoup(resposta.text, "html.parser")
        titulo = sopa.title.get_text(" ", strip=True) if sopa.title else "Sem titulo"
        texto = sopa.get_text(" ", strip=True).lower()
        bloqueado = any(p in (titulo.lower() + " " + texto[:3000]) for p in [
            "radware captcha", "access denied", "verify you are human"
        ])

        print("HTTP:", resposta.status_code)
        print("Titulo:", titulo)
        print("Links encontrados:", len(sopa.find_all("a", href=True)))
        print("Bloqueio detectado:", "SIM" if bloqueado else "NAO")

        if resposta.status_code == 200 and not bloqueado:
            print("RESULTADO: acesso basico OK")
        else:
            print("RESULTADO: acesso requer investigacao")
    except requests.RequestException as erro:
        print("RESULTADO: FALHA")
        print("Erro:", erro)
