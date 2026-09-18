import requests
from datetime import date, timedelta

hoje = date.today()
ini = hoje - timedelta(days=3)
base = "https://apitempo.inmet.gov.br"
urls = {
    "lista": f"{base}/estacoes/T",
    "A801": f"{base}/estacao/{ini}/{hoje}/A801",
    "D3224": f"{base}/estacao/{ini}/{hoje}/D3224",
}
for nome, url in urls.items():
    r = requests.get(url, timeout=60)
    print(f"{nome}: status {r.status_code}, {len(r.content)} bytes | {r.text[:120]}")

lista = requests.get(urls["lista"], timeout=60).json()
print("D3224 na lista?", any(e.get("CD_ESTACAO") == "D3224" for e in lista))