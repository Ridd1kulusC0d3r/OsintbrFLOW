#!/usr/bin/env python3
"""
SÓSIA 1.1 — radar de perfis imitadores
======================================

Sherlock, Maigret e similares procuram o username EXATO.
Quem aplica golpe não usa o nome exato: usa um nome QUASE igual.

    bancoaurora  →  banc0aurora, bancoaurora_oficial, bancoaurora.suporte ...

O SÓSIA gera essas variantes (letras trocadas por números parecidos,
sufixos de "suporte"/"oficial", as duas coisas juntas, pontos e sublinhados,
erros de digitação), verifica em quais plataformas elas já estão registradas,
lê o nome de exibição e a bio de cada perfil encontrado para ver se ele copia
o original ou oferece "suporte"/PIX, e mostra o que mudou desde a última busca.

Uso defensivo: proteção de marca, de executivos (VIP) e de perfis
institucionais contra imitação usada em phishing e golpes de suporte falso.

Só usa a biblioteca padrão do Python (3.9+). Nada para instalar.

Uso rápido
----------
    python sosia.py                        # modo guiado (pergunta tudo)
    python sosia.py bancoaurora            # gera variantes e verifica
    python sosia.py bancoaurora --so-gerar # só gera a lista, sem acessar nada
    python sosia.py --demo                 # caso de demonstração, sem internet
    python sosia.py marca --sites data.json --max 80   # data.json do Sherlock

Outras opções
-------------
    --max N            quantas variantes verificar (padrão: 60)
    --sem-perfil       não abre os perfis encontrados (só diz se existem)
    --saida PASTA      onde salvar (padrão: ./resultados)
    --sem-abrir        não abre o relatório no navegador no final

Licença MIT. Lista de sites: subconjunto do Sherlock Project (MIT).
"""
import csv
import difflib
import hashlib
import html
import json
import os
import random
import re
import string
import sys
import unicodedata
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

VERSAO = "1.1.0"
PASTA = os.path.dirname(os.path.abspath(__file__))
UA = f"Mozilla/5.0 (compatible; SOSIA/{VERSAO}; +brand protection)"


# ---------------------------------------------------------------------------
# 1. Gerador de variantes
# ---------------------------------------------------------------------------

# Trocas que enganam o olho (só ASCII: a maioria das plataformas só aceita isso)
HOMOGLIFOS = {
    "o": ["0"], "0": ["o"], "i": ["1", "l"], "l": ["1", "i"], "1": ["l", "i"],
    "e": ["3"], "a": ["4"], "s": ["5"], "5": ["s"], "g": ["9", "q"], "q": ["g"],
    "z": ["2"], "t": ["7"], "u": ["v"], "v": ["u"], "b": ["8"],
    "m": ["rn"], "rn": ["m"], "w": ["vv"], "vv": ["w"], "d": ["cl"], "cl": ["d"],
}

# Complementos que golpistas usam para parecer canal oficial ou de atendimento
ISCAS = ["_oficial", "oficial", ".oficial", "_official", "_suporte", "suporte", ".suporte",
         "_support", "_sac", "sac", "_atendimento", "_br", "br", "_real", "real",
         "_ajuda", "_help", "_adm", "_", "1"]
PREFIXOS = ["oficial", "real", "suporte", "the", "_"]
# Iscas usadas junto com um homóglifo (técnica combinada): as mais comuns em golpe
ISCAS_COMBINADAS = ["_suporte", "_oficial", "suporte", "oficial", "_sac", "_atendimento"]

# Peso = quão parecido com o original fica para quem olha rápido
TECNICAS = {
    "homoglifo":  (1.00, "troca por caractere parecido"),
    "combinada":  (1.00, "caractere parecido + 'oficial'/'suporte'"),
    "isca":       (0.95, "complemento de 'oficial' ou 'suporte'"),
    "separador":  (0.80, "ponto, sublinhado ou hífen a mais/a menos"),
    "duplicacao": (0.75, "letra repetida"),
    "omissao":    (0.70, "letra faltando"),
    "troca":      (0.70, "letras vizinhas invertidas"),
}


def variantes(original, maximo=60):
    """Gera variantes ordenadas por risco, alternando técnicas para manter variedade."""
    base = original.lower().lstrip("@")
    grupos = {t: [] for t in TECNICAS}

    def add(tecnica, v):
        if v and v != base and all(v != x for g in grupos.values() for x in g):
            grupos[tecnica].append(v)

    for chave, trocas in HOMOGLIFOS.items():
        for m in re.finditer(re.escape(chave), base):
            for troca in trocas:
                add("homoglifo", base[:m.start()] + troca + base[m.end():])
    for sufixo in ISCAS:
        add("isca", base + sufixo)
    # combinada: um homóglifo por vez, cada um com as iscas mais usadas
    for h in list(grupos["homoglifo"])[:4]:
        for sufixo in ISCAS_COMBINADAS:
            add("combinada", h + sufixo)
    for prefixo in PREFIXOS:
        add("isca", prefixo + base)
    for sep in "._-":
        add("separador", base.replace(sep, ""))
        for outro in "._-":
            if outro != sep and sep in base:
                add("separador", base.replace(sep, outro))
    # separador inserido: primeiro perto do meio, onde costuma ficar a divisão entre palavras
    for i in sorted(range(2, len(base) - 1), key=lambda i: abs(i - len(base) / 2)):
        if base[i - 1] not in "._-" and base[i] not in "._-":
            for sep in "_.":
                add("separador", base[:i] + sep + base[i:])
    for i in range(len(base)):
        add("duplicacao", base[:i + 1] + base[i] + base[i + 1:])
        if len(base) > 3:
            add("omissao", base[:i] + base[i + 1:])
        if i < len(base) - 1 and base[i] != base[i + 1]:
            add("troca", base[:i] + base[i + 1] + base[i] + base[i + 2:])

    # rodízio: metade do limite para as técnicas mais perigosas, depois uma de cada
    saida, filas = [], {t: list(v) for t, v in grupos.items()}
    perigosas = ("homoglifo", "isca", "combinada")
    while len(saida) < maximo // 2 and any(filas[t] for t in perigosas):
        for t in perigosas:
            if filas[t] and len(saida) < maximo // 2:
                saida.append((filas[t].pop(0), t))
    while len(saida) < maximo and any(filas.values()):
        for t in TECNICAS:
            if filas[t] and len(saida) < maximo:
                saida.append((filas[t].pop(0), t))
    return [{"variante": v, "tecnica": t, "peso": TECNICAS[t][0]} for v, t in saida]


def destacar(original, variante):
    """HTML com os caracteres diferentes do original marcados."""
    partes = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, original.lower(), variante).get_opcodes():
        trecho = html.escape(variante[b1:b2])
        partes.append(trecho if op == "equal" else f"<mark>{trecho}</mark>")
    return "".join(partes)


# ---------------------------------------------------------------------------
# 2. Rede e checagem (mesma lógica do Sherlock, simplificada)
# ---------------------------------------------------------------------------

class _NaoSeguir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def baixar(url, cabecalhos=None, seguir=True, timeout=15):
    """GET simples. Devolve (status, texto). status=None quando a rede falha."""
    pedido = urllib.request.Request(url, headers={"User-Agent": UA, **(cabecalhos or {})})
    abridor = urllib.request.build_opener() if seguir else urllib.request.build_opener(_NaoSeguir)
    try:
        with abridor.open(pedido, timeout=timeout) as r:
            return r.status, r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            corpo = e.read(100_000).decode("utf-8", "replace")
        except Exception:
            corpo = ""
        return e.code, corpo
    except Exception as e:
        return None, str(e)


def carregar_sites(caminho=None):
    """Lê um arquivo no formato do data.json do Sherlock."""
    caminho = caminho or os.path.join(PASTA, "sites_padrao.json")
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return {n: s for n, s in dados.items()
            if isinstance(s, dict) and "{}" in s.get("url", "")
            and not s.get("request_payload") and not s.get("isNSFW")}


def como_lista(valor):
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def checar(site, usuario, rede=baixar):
    """'EXISTE', 'NAO_EXISTE', 'INCONCLUSIVO' ou 'INVALIDO' (o site não aceita esse nome)."""
    regex = site.get("regexCheck")
    if regex and not re.search(regex, usuario):
        return "INVALIDO"
    tipos = como_lista(site.get("errorType", "status_code"))
    url = (site.get("urlProbe") or site["url"]).replace("{}", usuario)
    status, corpo = rede(url, site.get("headers"), "response_url" not in tipos)
    codigos = [int(c) for c in como_lista(site.get("errorCode"))]

    if status is None:
        return "INCONCLUSIVO"
    if status not in codigos and (status in (401, 403, 429) or status >= 500):
        return "INCONCLUSIVO"
    if "cf-chl" in corpo or "Just a moment..." in corpo:
        return "INCONCLUSIVO"
    ausente = False
    for t in tipos:
        if t == "status_code":
            ausente |= status in codigos or not 200 <= status < 300
        elif t == "message":
            ausente |= any(m in corpo for m in como_lista(site.get("errorMsg")))
        elif t == "response_url":
            ausente |= not 200 <= status < 300
    return "NAO_EXISTE" if ausente else "EXISTE"


def nome_impossivel():
    """Um username que ninguém registrou, para testar se o site mente (soft-404)."""
    return "zq" + "".join(random.choice(string.ascii_lowercase) for _ in range(12))


def varrer_site(nome, site, original, lista, rede, pausa):
    """Verifica todas as variantes em um site, com uma linha de base antes."""
    controle = checar(site, nome_impossivel(), rede)
    info = {"site": nome, "url": site["url"], "controle": controle,
            "original": checar(site, original, rede), "resultados": {}}
    if controle == "EXISTE":
        info["confiavel"], info["motivo"] = False, "responde 'existe' até para nome impossível"
        return info
    if controle == "INCONCLUSIVO" and info["original"] == "INCONCLUSIVO":
        info["confiavel"], info["motivo"] = False, "inacessível agora (bloqueio ou sem rede)"
        return info
    info["confiavel"], info["motivo"] = True, ""
    for v in lista:
        info["resultados"][v["variante"]] = checar(site, v["variante"], rede)
        time.sleep(pausa)
    return info


def varrer(original, lista, sites, rede=baixar, pausa=0.3, trabalhadores=6, mostrar=None):
    """Um site por vez em cada linha de execução: educado com cada plataforma."""
    mostrar = mostrar or print
    with ThreadPoolExecutor(max_workers=trabalhadores) as ex:
        tarefas = {nome: ex.submit(varrer_site, nome, s, original.lower(), lista, rede, pausa)
                   for nome, s in sites.items()}
        saida = []
        for nome, tarefa in tarefas.items():
            info = tarefa.result()
            achados = [v for v, r in info["resultados"].items() if r == "EXISTE"]
            if info["confiavel"]:
                lista_txt = ", ".join(achados[:4]) + (" ..." if len(achados) > 4 else "")
                mostrar(f"  {nome:<14} {len(achados)} sósia(s)   {lista_txt}")
            else:
                mostrar(f"  {nome:<14} DESCARTADO: {info['motivo']}")
            saida.append(info)
    if saida and not any(i["confiavel"] for i in saida):
        mostrar("\n  Nenhuma plataforma respondeu de forma confiável. Verifique a internet, VPN ou proxy.\n"
                "  Para ver a ferramenta funcionando sem internet: python sosia.py --demo")
    return saida


# ---------------------------------------------------------------------------
# 3. Leitura do perfil encontrado (nome de exibição e bio)
# ---------------------------------------------------------------------------

_META = re.compile(
    r'<meta\s[^>]*?(?:property|name)\s*=\s*["\'](og:title|og:description|twitter:title|'
    r'twitter:description|description)["\'][^>]*?content\s*=\s*["\']([^"\']*)["\']'
    r'|<meta\s[^>]*?content\s*=\s*["\']([^"\']*)["\'][^>]*?(?:property|name)\s*=\s*["\']'
    r'(og:title|og:description|twitter:title|twitter:description|description)["\']',
    re.I)
_TITULO = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

# Palavras de golpe de atendimento falso / pagamento na bio
_ISCA_BIO = re.compile(
    r"\b(suporte|atendimento|sac|whats\w*|wa\.me|pix|direct|dm|inbox|sorteio|promo\w*|"
    r"resgat\w*|desbloque\w*|estorno|reembolso|bit\.ly|t\.me|link na bio)\b")


def normalizar(texto):
    """minúsculas, sem acento, só letras e números: 'Banco Aurora!' -> 'bancoaurora'."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def extrair_perfil(corpo):
    """Tira nome de exibição e bio das etiquetas que as plataformas publicam para prévia de link."""
    campos = {}
    for m in _META.finditer(corpo or ""):
        chave = (m.group(1) or m.group(4)).lower()
        valor = html.unescape(m.group(2) if m.group(1) else m.group(3)).strip()
        campos.setdefault(chave, valor)
    titulo = campos.get("og:title") or campos.get("twitter:title")
    if not titulo:
        t = _TITULO.search(corpo or "")
        titulo = html.unescape(t.group(1)).strip() if t else ""
    # "Banco Aurora (@bancoaurora) • Instagram" -> "Banco Aurora"
    nome = re.split(r"\s+[•|·–-]\s+|\s*\(@", titulo)[0].strip() if titulo else ""
    bio = campos.get("og:description") or campos.get("twitter:description") or campos.get("description") or ""
    return {"nome": nome[:120], "bio": re.sub(r"\s+", " ", bio)[:300]}


def ler_perfil(site, usuario, rede=baixar, nome_site=""):
    """Abre a página pública do perfil. None se não deu para ler (login, bloqueio, sem etiquetas)."""
    status, corpo = rede(site["url"].replace("{}", usuario), site.get("headers"), True)
    if status != 200:
        return None
    perfil = extrair_perfil(corpo)
    # página de login costuma ter só o nome da plataforma como título
    dominio = re.search(r"//(?:www\.)?([^./{]+)", site["url"])
    genericos = {normalizar(nome_site), dominio.group(1).lower() if dominio else "", "login", "entrar", "signin"}
    if normalizar(perfil["nome"]) in genericos:
        perfil["nome"] = ""
    return perfil if (perfil["nome"] or perfil["bio"]) else None


def avaliar_perfil(original, perfil_original, perfil):
    """
    Compara o perfil do sósia com o do original. Devolve (sinais, critico).
    Crítico = copia o nome/bio do original, ou usa a marca no nome E oferece contato/pagamento.
    """
    if not perfil:
        return [], False
    sinais, forte, usa_marca = [], False, False
    marca = normalizar(original)
    nome_s, nome_o = normalizar(perfil["nome"]), normalizar((perfil_original or {}).get("nome"))
    if nome_o and nome_s and difflib.SequenceMatcher(None, nome_o, nome_s).ratio() >= 0.85:
        sinais.append("nome de exibição igual ao do original")
        forte = True
    elif marca and len(marca) >= 4 and marca in nome_s:
        sinais.append("nome de exibição usa a marca")
        usa_marca = True
    bio_s, bio_o = sem_acento(perfil["bio"]), sem_acento((perfil_original or {}).get("bio"))
    if bio_o and bio_s and difflib.SequenceMatcher(None, bio_o, bio_s).ratio() >= 0.7:
        sinais.append("bio copiada do original")
        forte = True
    iscas = sorted(set(_ISCA_BIO.findall(bio_s)))
    if iscas:
        sinais.append("bio oferece contato/pagamento: " + ", ".join(iscas[:5]))
    return sinais, forte or ((usa_marca or forte) and bool(iscas))


def analisar_perfis(original, achados, sites, varredura, rede=baixar, pausa=0.3, mostrar=None):
    """Lê o perfil de cada sósia encontrado e do original na mesma plataforma; ajusta o risco."""
    mostrar = mostrar or print
    if not achados:
        return achados
    originais = {}
    for info in varredura:
        if info["confiavel"] and info["original"] == "EXISTE" and info["site"] in sites:
            originais[info["site"]] = ler_perfil(sites[info["site"]], original.lower(), rede, info["site"])
            time.sleep(pausa)
    legiveis = criticos = 0
    for a in achados:
        perfil = ler_perfil(sites[a["site"]], a["variante"], rede, a["site"]) if a["site"] in sites else None
        time.sleep(pausa)
        sinais, critico = avaliar_perfil(original, originais.get(a["site"]), perfil)
        a["perfil_nome"] = perfil["nome"] if perfil else ""
        a["perfil_bio"] = perfil["bio"] if perfil else ""
        a["perfil_legivel"] = bool(perfil)
        a["sinais"] = sinais
        legiveis += bool(perfil)
        if critico:
            a["risco"], a["peso"] = "CRÍTICO", 1.1
            criticos += 1
    mostrar(f"\n  Perfis lidos: {legiveis} de {len(achados)} · CRÍTICOS (imitam o original): {criticos}")
    return sorted(achados, key=lambda a: (-a["peso"], a["variante"], a["site"]))


# ---------------------------------------------------------------------------
# 4. Monitoramento: o que mudou desde a última busca
# ---------------------------------------------------------------------------

def _seguro(original):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", original)


def execucao_anterior(pasta_base, original):
    """Última busca completa da mesma marca nesta pasta de resultados (ou None)."""
    if not os.path.isdir(pasta_base):
        return None
    prefixo = f"sosia_{_seguro(original)}_"
    for nome in sorted((d for d in os.listdir(pasta_base) if d.startswith(prefixo)), reverse=True):
        caminho = os.path.join(pasta_base, nome, "dados.json")
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, ValueError):
            continue
        if dados.get("meta", {}).get("modo") == "verificação":
            return {"gerado_em_utc": dados["meta"]["gerado_em_utc"], "pasta": nome,
                    "achados": [[a["variante"], a["site"]] for a in dados.get("achados", [])]}
    return None


def comparar(anterior, achados, varredura):
    """Marca os achados novos e lista os que sumiram (só onde a plataforma foi verificada agora)."""
    if not anterior:
        for a in achados:
            a["novo"] = False
        return None
    antes = {tuple(x) for x in anterior["achados"]}
    for a in achados:
        a["novo"] = (a["variante"], a["site"]) not in antes
    resultados = {i["site"]: i["resultados"] for i in varredura if i["confiavel"]}
    sumiram = [{"variante": v, "site": s} for v, s in sorted(antes)
               if resultados.get(s, {}).get(v) == "NAO_EXISTE"]
    return {"desde_utc": anterior["gerado_em_utc"], "origem": anterior.get("pasta", ""),
            "novos": sum(1 for a in achados if a["novo"]), "sumiram": sumiram}


# ---------------------------------------------------------------------------
# 5. Saídas: JSON, CSV, lista de vigilância, manifesto e relatório HTML
# ---------------------------------------------------------------------------

def risco(peso):
    return "ALTO" if peso >= 0.95 else "MÉDIO" if peso >= 0.75 else "BAIXO"


def achados_de(original, lista, varredura):
    por_nome = {v["variante"]: v for v in lista}
    achados = []
    for info in varredura:
        for variante, estado in info["resultados"].items():
            if estado == "EXISTE":
                v = por_nome[variante]
                achados.append({"variante": variante, "site": info["site"], "tecnica": v["tecnica"],
                                "risco": risco(v["peso"]), "peso": v["peso"],
                                "url": info["url"].replace("{}", variante),
                                "perfil_nome": "", "perfil_bio": "", "perfil_legivel": False,
                                "sinais": [], "novo": False})
    return sorted(achados, key=lambda a: (-a["peso"], a["variante"], a["site"]))


def sha256(caminho):
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def salvar(original, lista, varredura, pasta_base, fonte_sites, achados=None, comparacao=None):
    agora = datetime.now(timezone.utc)
    pasta = os.path.join(pasta_base, f"sosia_{_seguro(original)}_{agora.strftime('%Y%m%d-%H%M%S')}")
    n = 1
    while os.path.exists(pasta + (f"-{n}" if n > 1 else "")):
        n += 1
    pasta += f"-{n}" if n > 1 else ""
    os.makedirs(pasta)
    if achados is None:
        achados = achados_de(original, lista, varredura) if varredura else []
    meta = {"ferramenta": f"SÓSIA {VERSAO}", "original": original,
            "gerado_em_utc": agora.strftime("%Y-%m-%d %H:%M:%S"),
            "variantes_verificadas": len(lista), "plataformas": len(varredura),
            "fonte_sites": fonte_sites, "modo": "verificação" if varredura else "só geração"}

    arquivos = {}
    arquivos["variantes.txt"] = os.path.join(pasta, "variantes.txt")
    with open(arquivos["variantes.txt"], "w", encoding="utf-8") as f:
        f.write("\n".join(v["variante"] for v in lista) + "\n")
    arquivos["dados.json"] = os.path.join(pasta, "dados.json")
    with open(arquivos["dados.json"], "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "variantes": lista, "varredura": varredura, "achados": achados,
                   "comparacao": comparacao}, f, ensure_ascii=False, indent=2)
    arquivos["achados.csv"] = os.path.join(pasta, "achados.csv")
    with open(arquivos["achados.csv"], "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["risco", "novo", "variante", "site", "tecnica", "perfil_nome",
                                          "sinais", "perfil_bio", "url"], extrasaction="ignore")
        w.writeheader()
        for a in achados:
            w.writerow({**a, "novo": "sim" if a.get("novo") else "", "sinais": " | ".join(a.get("sinais", []))})
    if comparacao:
        arquivos["mudancas.csv"] = os.path.join(pasta, "mudancas.csv")
        with open(arquivos["mudancas.csv"], "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["situacao", "risco", "variante", "site", "url"])
            for a in achados:
                if a.get("novo"):
                    w.writerow(["NOVO", a["risco"], a["variante"], a["site"], a["url"]])
            for x in comparacao["sumiram"]:
                w.writerow(["SUMIU", "", x["variante"], x["site"], ""])

    hashes = {n: sha256(p) for n, p in arquivos.items()}
    with open(os.path.join(pasta, "manifesto.txt"), "w", encoding="utf-8") as f:
        f.write(f"{meta['ferramenta']} | {original} | {meta['gerado_em_utc']} UTC\n")
        for n, h in hashes.items():
            f.write(f"SHA-256  {h}  {n}\n")
    relatorio = os.path.join(pasta, "relatorio.html")
    with open(relatorio, "w", encoding="utf-8") as f:
        f.write(relatorio_html(meta, lista, varredura, achados, hashes, comparacao))
    return pasta, relatorio, achados


SIMBOLO = {"EXISTE": ("●", "existe", "registrado"), "NAO_EXISTE": ("·", "livre", "livre"),
           "INCONCLUSIVO": ("?", "incerto", "inconclusivo"), "INVALIDO": ("", "invalido", "formato não aceito")}
CLASSE_RISCO = {"CRÍTICO": "r-c", "ALTO": "r-a", "MÉDIO": "r-m", "BAIXO": "r-b"}


def data_br(utc):
    return f"{utc[8:10]}/{utc[5:7]}/{utc[0:4]} {utc[11:16]} UTC" if utc else ""


def celula_perfil(a):
    if not a.get("perfil_legivel"):
        return '<span class="vazio">não legível sem login</span>' if "perfil_legivel" in a else "—"
    partes = []
    if a["perfil_nome"]:
        partes.append(f'<b>{html.escape(a["perfil_nome"])}</b>')
    if a["perfil_bio"]:
        bio = a["perfil_bio"]
        partes.append(f'<span class="bio">{html.escape(bio[:140])}{"…" if len(bio) > 140 else ""}</span>')
    if a["sinais"]:
        partes.append('<ul class="sinais">' + "".join(f"<li>{html.escape(x)}</li>" for x in a["sinais"]) + "</ul>")
    return "".join(partes)


def bloco_mudancas(comparacao, achados):
    if comparacao is None:
        return ('<h2>Desde a última verificação</h2><p class="sub">Primeira verificação desta marca nesta pasta. '
                'Rode de novo daqui a alguns dias (ou agende): esta seção vai mostrar os sósias <b>novos</b> '
                'e os que <b>sumiram</b>.</p>')
    novos = [a for a in achados if a.get("novo")]
    itens = "".join(f'<li><span class="selo novo">NOVO</span> <span class="mono">{html.escape(a["variante"])}</span> '
                    f'em {html.escape(a["site"])} · {a["risco"]}</li>' for a in novos)
    itens += "".join(f'<li><span class="selo sumiu">SUMIU</span> <span class="mono">{html.escape(x["variante"])}</span> '
                     f'em {html.escape(x["site"])} (removido, renomeado ou derrubado)</li>' for x in comparacao["sumiram"])
    vazio = '<li class="vazio">Nada mudou.</li>'
    return (f'<h2>Desde a última verificação <span class="sub">({data_br(comparacao["desde_utc"])})</span></h2>'
            f'<div class="painel"><ul class="mudancas">{itens or vazio}</ul></div>')


def relatorio_html(meta, lista, varredura, achados, hashes, comparacao=None):
    original = meta["original"]
    confiaveis = [i for i in varredura if i["confiavel"]]
    descartados = [f'{i["site"]} ({i.get("motivo", "")})' for i in varredura if not i["confiavel"]]
    descartadas_txt = f" · descartadas: {html.escape('; '.join(descartados))}" if descartados else ""
    critico = sum(1 for a in achados if a["risco"] == "CRÍTICO")
    alto = sum(1 for a in achados if a["risco"] == "ALTO")
    novos = sum(1 for a in achados if a.get("novo"))

    selo_novo = ' <span class="selo novo">NOVO</span>'
    linhas = []
    for a in achados:
        classe_linha = "l-critico" if a["risco"] == "CRÍTICO" else ""
        linhas.append(
            f'<tr class="{classe_linha}">'
            f'<td><span class="selo {CLASSE_RISCO[a["risco"]]}">{a["risco"]}</span></td>'
            f'<td><span class="mono">{destacar(original, a["variante"])}</span>'
            f'{selo_novo if a.get("novo") else ""}'
            f'<br><small class="vazio">{TECNICAS[a["tecnica"]][1]}</small></td>'
            f'<td>{html.escape(a["site"])}</td><td class="perfil">{celula_perfil(a)}</td>'
            f'<td><a href="{html.escape(a["url"])}" target="_blank" rel="noopener">abrir</a></td></tr>')
    linhas_achados = "".join(linhas) or ('<tr><td colspan="5" class="vazio">Nenhuma variante registrada '
                                         'nas plataformas verificadas.</td></tr>')

    mostrar = [v for v in lista if any(i["resultados"].get(v["variante"]) in ("EXISTE", "INCONCLUSIVO")
                                       for i in confiaveis)]
    cab = "".join(f'<th class="vert"><span>{html.escape(i["site"])}</span></th>' for i in confiaveis)
    orig = "".join(f'<td class="c {SIMBOLO.get(i["original"], ("", "", ""))[1]}" '
                   f'title="{html.escape(i["site"])}: {SIMBOLO.get(i["original"], ("", "", i["original"]))[2]}">'
                   f'{SIMBOLO.get(i["original"], ("",))[0]}</td>' for i in confiaveis)
    corpo = []
    for v in mostrar:
        celulas = "".join(
            f'<td class="c {SIMBOLO[i["resultados"].get(v["variante"], "INVALIDO")][1]}" '
            f'title="{html.escape(i["site"])}: {SIMBOLO[i["resultados"].get(v["variante"], "INVALIDO")][2]}">'
            f'{SIMBOLO[i["resultados"].get(v["variante"], "INVALIDO")][0]}</td>' for i in confiaveis)
        corpo.append(f'<tr><td class="mono">{destacar(original, v["variante"])}</td>{celulas}</tr>')
    matriz = (f'<table class="matriz"><thead><tr><th></th>{cab}</tr></thead><tbody>'
              f'<tr class="orig"><td class="mono"><b>{html.escape(original)}</b> (original)</td>{orig}</tr>'
              f'{"".join(corpo)}</tbody></table>') if confiaveis else '<p class="vazio">Sem plataformas verificadas.</p>'

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SÓSIA · {html.escape(original)}</title>
<style>
:root {{ --fundo:#f3f4f6; --papel:#fff; --tinta:#14171c; --suave:#5f6672; --linha:#dfe2e7;
  --critico:#8f1d14; --alto:#c2362b; --medio:#b7791f; --baixo:#5f6672; --marca:#ffe08a; --livre:#c9ced6; --novo:#1f6feb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fundo:#0f1115; --papel:#181b21; --tinta:#e8eaee;
  --suave:#9aa1ad; --linha:#2a2f38; --critico:#ff8a80; --alto:#ff6b5e; --medio:#f0b252; --baixo:#9aa1ad;
  --marca:#6b5a1d; --livre:#3a404b; --novo:#79b8ff; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--fundo); color:var(--tinta);
  font:15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif }}
main {{ max-width:1000px; margin:0 auto; padding:32px 16px 64px }}
.marca-topo {{ letter-spacing:.18em; font-size:12px; color:var(--suave); text-transform:uppercase }}
h1 {{ font:800 30px/1.1 ui-monospace, "SF Mono", Menlo, Consolas, monospace; margin:2px 0 0 }}
h2 {{ font-size:18px; margin:36px 0 12px }} h2 .sub {{ font-weight:400; font-size:14px }}
.sub, .vazio {{ color:var(--suave) }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-top:24px }}
.card {{ background:var(--papel); border:1px solid var(--linha); border-radius:10px; padding:14px }}
.card b {{ display:block; font:800 28px/1 ui-monospace, Menlo, monospace }}
.card span {{ color:var(--suave); font-size:13px }}
.card.critico {{ border-color:var(--critico) }} .card.critico b {{ color:var(--critico) }}
.card.alto b {{ color:var(--alto) }} .card.novo b {{ color:var(--novo) }}
.painel {{ background:var(--papel); border:1px solid var(--linha); border-radius:10px; padding:16px; overflow-x:auto }}
table {{ width:100%; border-collapse:collapse; font-size:14px }}
th, td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--linha); vertical-align:top }}
th {{ color:var(--suave); font-size:12px; text-transform:uppercase; letter-spacing:.06em; font-weight:600 }}
.mono {{ font-family:ui-monospace, "SF Mono", Menlo, Consolas, monospace; white-space:nowrap }}
mark {{ background:var(--marca); color:inherit; border-radius:3px; padding:0 1px }}
a {{ color:inherit }}
.selo {{ font-size:11px; font-weight:700; letter-spacing:.05em; padding:2px 7px; border-radius:99px;
  border:1px solid currentColor; white-space:nowrap }}
.r-c {{ color:#fff; background:var(--critico); border-color:var(--critico) }}
.r-a {{ color:var(--alto) }} .r-m {{ color:var(--medio) }} .r-b {{ color:var(--baixo) }}
.selo.novo {{ color:var(--novo) }} .selo.sumiu {{ color:var(--suave) }}
tr.l-critico td {{ background:color-mix(in srgb, var(--critico) 6%, transparent) }}
td.perfil {{ min-width:220px; max-width:340px }}
.bio {{ display:block; color:var(--suave); font-size:13px }}
ul.sinais {{ margin:4px 0 0; padding-left:18px; color:var(--critico); font-size:13px }}
ul.mudancas {{ margin:0; padding-left:0; list-style:none }} ul.mudancas li {{ padding:5px 0 }}
.matriz {{ width:auto }} .matriz td, .matriz th {{ border-bottom:1px solid var(--linha); padding:4px 6px; vertical-align:middle }}
.matriz th.vert {{ height:110px; vertical-align:bottom; padding:0 }}
.matriz th.vert span {{ display:block; writing-mode:vertical-rl; transform:rotate(180deg); padding:6px 4px;
  text-transform:none; letter-spacing:0; font-size:12px }}
.c {{ text-align:center; width:30px; font-weight:700 }}
.c.existe {{ color:var(--alto); font-size:18px }} .c.livre {{ color:var(--livre) }} .c.incerto {{ color:var(--medio) }}
tr.orig td {{ background:color-mix(in srgb, var(--linha) 45%, transparent) }}
tr.orig .c.existe {{ color:var(--tinta) }}
.aviso {{ border-left:3px solid var(--medio); padding:4px 0 4px 14px; color:var(--suave) }}
.rodape {{ font-size:12px; color:var(--suave); margin-top:40px; word-break:break-all }}
@media (max-width:640px) {{
  .achados thead {{ display:none }}
  .achados tr {{ display:block; padding:10px 4px; border-bottom:1px solid var(--linha) }}
  .achados td {{ display:block; border:none; padding:3px 0 }}
  .achados td.perfil {{ min-width:0; max-width:none }}
  .achados td:nth-child(3)::before {{ content:"Plataforma: "; color:var(--suave) }}
}}
</style></head><body><main>
<div class="marca-topo">SÓSIA · radar de perfis imitadores</div>
<h1>{html.escape(original)}</h1>
<p class="sub">Gerado em {meta['gerado_em_utc']} UTC · {meta['variantes_verificadas']} variantes ·
{len(confiaveis)} plataformas confiáveis hoje{descartadas_txt}</p>

<div class="cards">
  <div class="card critico"><b>{critico}</b><span>CRÍTICOS: imitam o perfil original</span></div>
  <div class="card alto"><b>{alto}</b><span>sósias de risco ALTO</span></div>
  <div class="card novo"><b>{novos if comparacao else '—'}</b><span>novos desde a última verificação</span></div>
  <div class="card"><b>{len(achados)}</b><span>registros de variantes no total</span></div>
</div>

{bloco_mudancas(comparacao, achados) if varredura else ''}

<h2>Sósias encontrados</h2>
<div class="painel"><table class="achados">
<thead><tr><th>Risco</th><th>Variante</th><th>Plataforma</th><th>Perfil (nome · bio · sinais)</th><th>Link</th></tr></thead>
<tbody>{linhas_achados}</tbody></table></div>
<p class="sub">Em <mark>destaque</mark>: o que muda em relação a <b>{html.escape(original)}</b>.
CRÍTICO = o perfil copia o nome ou a bio do original, ou usa a marca no nome e oferece contato/pagamento.</p>

<h2>Mapa de calor</h2>
<div class="painel">{matriz}</div>
<p class="sub"><b style="color:var(--alto)">●</b> registrado · <b style="color:var(--livre)">·</b> livre ·
<b style="color:var(--medio)">?</b> inconclusivo (bloqueio ou limite de acesso) · vazio = formato não aceito pela plataforma.
A primeira linha mostra o próprio original. Só aparecem variantes com algum registro ou dúvida.</p>

<h2>Como ler este relatório</h2>
<p class="aviso">Registrado não quer dizer golpe. Muitos nomes parecidos pertencem a pessoas comuns ou à própria
marca (contas reserva). Comece pelos <b>CRÍTICOS</b>: o SÓSIA leu a página pública e encontrou nome ou bio copiados,
ou a marca no nome junto com oferta de "suporte", PIX ou WhatsApp. Mesmo assim, abra o link e confirme antes de
denunciar. "Não legível sem login" quer dizer que a plataforma não mostra nome e bio a visitantes: abra você mesmo.
"Livre" significa que o nome pode ser registrado por qualquer pessoa hoje: considere registrar os mais perigosos
antes de um golpista. A lista completa de variantes está em <b>variantes.txt</b>.</p>

<div class="rodape">{meta['ferramenta']} · fonte da lista de sites: {html.escape(meta['fonte_sites'])}<br>
{'<br>'.join(f'SHA-256 {h} · {n}' for n, h in hashes.items())}</div>
</main></body></html>"""


# ---------------------------------------------------------------------------
# 6. Caso de demonstração (funciona sem internet)
# ---------------------------------------------------------------------------

def rede_demo(sites, caminho=None):
    """Simula as plataformas a partir de demo/caso_demo.json. Devolve (original, rede, anterior)."""
    with open(caminho or os.path.join(PASTA, "demo", "caso_demo.json"), encoding="utf-8") as f:
        caso = json.load(f)
    erros = " ".join(m for s in sites.values() for m in como_lista(s.get("errorMsg")))
    paginas = {**caso["registrados"], **caso.get("paginas_de_perfil", {})}

    def rede(url, *args, **kwargs):
        for prefixo, resposta in caso.get("sites_que_mentem", {}).items():
            if url.startswith(prefixo):
                return resposta["status"], resposta["corpo"]
        if url in paginas:
            r = paginas[url]
            return r["status"], r["corpo"]
        return 404, erros  # qualquer outro nome: "não existe"
    return caso["original"], rede, caso.get("execucao_anterior")


# ---------------------------------------------------------------------------
# 7. Linha de comando
# ---------------------------------------------------------------------------

def opcao(argv, nome, padrao=None):
    return argv[argv.index(nome) + 1] if nome in argv and argv.index(nome) + 1 < len(argv) else padrao


def main(argv):
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    if "--versao" in argv:
        print(VERSAO)
        return 0

    guiado = len(argv) == 0
    valores = {opcao(argv, o) for o in ("--sites", "--saida", "--max")}
    posicionais = [a for a in argv if not a.startswith("--") and a not in valores]
    original = posicionais[0].lstrip("@") if posicionais else None
    so_gerar = "--so-gerar" in argv
    demo = "--demo" in argv
    if guiado:
        print(f"\nSÓSIA {VERSAO} — radar de perfis imitadores\n")
        original = input("Username da marca ou pessoa a proteger (ou DEMO para o exemplo): ").strip().lstrip("@")
        if original.upper() == "DEMO":
            demo = True
        elif original:
            so_gerar = input("Só gerar a lista, sem acessar as plataformas? [s/N]: ").strip().lower().startswith("s")
    if not original and not demo:
        print(__doc__)
        return 1

    fonte = opcao(argv, "--sites")
    sites = carregar_sites(fonte)
    rotulo = os.path.basename(fonte) if fonte else "sites_padrao.json (Sherlock, subconjunto)"
    pasta_base = opcao(argv, "--saida", os.path.join(os.getcwd(), "resultados"))
    rede, pausa, anterior_demo = baixar, 0.3, None
    if demo:
        original, rede, anterior_demo = rede_demo(sites)
        pausa = 0

    lista = variantes(original, int(opcao(argv, "--max", "60")))
    print(f"\nSÓSIA :: {original} :: {len(lista)} variantes :: "
          f"{'só geração' if so_gerar else f'{len(sites)} plataformas'}{' :: DEMONSTRAÇÃO' if demo else ''}\n")
    varredura, achados, comparacao = [], [], None
    if not so_gerar:
        anterior = anterior_demo if demo else execucao_anterior(pasta_base, original)
        varredura = varrer(original, lista, sites, rede, pausa)
        achados = achados_de(original, lista, varredura)
        if "--sem-perfil" not in argv:
            achados = analisar_perfis(original, achados, sites, varredura, rede, pausa)
        comparacao = comparar(anterior, achados, varredura)
        if comparacao:
            print(f"  Desde {data_br(comparacao['desde_utc'])}: {comparacao['novos']} novo(s), "
                  f"{len(comparacao['sumiram'])} sumiu(ram)")
    pasta, relatorio, achados = salvar(original, lista, varredura, pasta_base, rotulo, achados, comparacao)

    conta = {r: sum(1 for a in achados if a["risco"] == r) for r in ("CRÍTICO", "ALTO")}
    print(f"\nSósias registrados: {len(achados)} (CRÍTICO: {conta['CRÍTICO']}, ALTO: {conta['ALTO']})")
    print(f"Relatório: {relatorio}")
    if "--sem-abrir" not in argv:
        webbrowser.open("file://" + os.path.abspath(relatorio))
    if guiado:
        input("\nPressione Enter para sair.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
