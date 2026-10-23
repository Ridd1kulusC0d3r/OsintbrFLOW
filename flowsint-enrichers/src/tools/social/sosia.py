#!/usr/bin/env python3
"""
SÓSIA 1.3 — radar de perfis imitadores
======================================

Sherlock, Maigret e similares procuram o username EXATO.
Quem aplica golpe não usa o nome exato: usa um nome QUASE igual.

    bancoaurora  →  banc0aurora, bancoaurora_oficial, bancoaurora.suporte ...

O SÓSIA gera essas variantes (letras trocadas por números parecidos,
sufixos de "suporte"/"oficial", as duas coisas juntas, pontos e sublinhados,
erros de digitação), verifica em quais plataformas elas já estão registradas,
lê o nome de exibição e a bio de cada perfil encontrado para ver se ele copia
o original ou oferece "suporte"/PIX, liga perfis que publicam o mesmo WhatsApp,
PIX ou link (mesma operação), guarda as páginas como evidência com SHA-256,
prepara a denúncia e mostra o que mudou desde a última busca.

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

O que sai em cada busca (pasta resultados/)
--------------------------------------------
    relatorio.html     abra este primeiro
    denuncia.md        rascunho de denúncia por plataforma (canal oficial + texto + evidência)
    achados.csv        sósias encontrados        contatos.csv   WhatsApp, PIX, e-mail, links das bios
    mudancas.csv       NOVO / SUMIU              evidencias/    páginas lidas, como chegaram (.txt)
    achados.stix.json  STIX 2.1 para OpenCTI/MISP
    manifesto.txt      SHA-256 de tudo

Opções mais usadas (todas em: python sosia.py --help)
-----------------------------------------------------
    --oficiais A,B     contas da própria marca: nunca viram sósia
    --plataformas A,B  só estas plataformas      --extra   + X (Twitter), Pinterest, Reddit, Snapchat, Patreon
    --max N            quantas variantes verificar (padrão: 60)
    --sem-perfil       não abre os perfis encontrados (só diz se existem)
    --saida PASTA      onde salvar (padrão: ./resultados)
    --sem-abrir        não abre o relatório no navegador no final
    --alerta           para agendar: sai com código 2 se houver CRÍTICO/ALTO novo

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
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

VERSAO = "1.3.0"
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


ESPERA_MAXIMA = 8  # segundos: o máximo que o SÓSIA espera quando a plataforma pede calma (429/503)


def _uma_vez(url, cabecalhos, seguir, timeout):
    pedido = urllib.request.Request(url, headers={"User-Agent": UA, **(cabecalhos or {})})
    abridor = urllib.request.build_opener() if seguir else urllib.request.build_opener(_NaoSeguir)
    try:
        with abridor.open(pedido, timeout=timeout) as r:
            return r.status, r.read(400_000).decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        try:
            corpo = e.read(100_000).decode("utf-8", "replace")
        except Exception:
            corpo = ""
        return e.code, corpo, (e.headers or {}).get("Retry-After")
    except Exception as e:
        return None, str(e), None


def tempo_de_espera(retry_after):
    """Segundos a esperar a partir do cabeçalho Retry-After (número ou ausente), entre 1 e ESPERA_MAXIMA."""
    try:
        return max(1.0, min(float(retry_after), ESPERA_MAXIMA))
    except (TypeError, ValueError):
        return 2.0


def baixar(url, cabecalhos=None, seguir=True, timeout=15):
    """
    GET simples. Devolve (status, texto). status=None quando a rede falha.
    Se a plataforma responder 429 ou 503 (limite de acesso), espera o que ela pedir (até 8 s)
    e tenta UMA vez de novo; se continuar limitando, o resultado vira INCONCLUSIVO em checar().
    """
    status, corpo, retry_after = _uma_vez(url, cabecalhos, seguir, timeout)
    if status in (429, 503):
        time.sleep(tempo_de_espera(retry_after))
        status, corpo, _ = _uma_vez(url, cabecalhos, seguir, timeout)
    return status, corpo


def carregar_sites(caminho=None, extra=False, plataformas=None):
    """
    Lê um arquivo no formato do data.json do Sherlock (padrão: sites_padrao.json, 12 plataformas).
    extra=True junta sites_extra.json (Twitter/X, Pinterest, Reddit, Snapchat, Patreon).
    plataformas: nomes a manter (sem diferenciar maiúsculas); ValueError se algum não existir.
    """
    caminhos = [caminho or os.path.join(PASTA, "sites_padrao.json")]
    if extra:
        caminhos.append(os.path.join(PASTA, "sites_extra.json"))
    dados = {}
    for c in caminhos:
        with open(c, encoding="utf-8") as f:
            dados.update(json.load(f))
    sites = {n: s for n, s in dados.items()
             if isinstance(s, dict) and "{}" in s.get("url", "")
             and not s.get("request_payload") and not s.get("isNSFW")}
    if plataformas:
        por_nome = {n.lower(): n for n in sites}
        faltam = [p for p in plataformas if p.strip().lower() not in por_nome]
        if faltam:
            raise ValueError(f"plataforma(s) desconhecida(s): {', '.join(faltam)}. "
                             f"Disponíveis: {', '.join(sorted(sites))}")
        sites = {por_nome[p.strip().lower()]: sites[por_nome[p.strip().lower()]] for p in plataformas}
    return sites


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


LIMITES_SEGUIDOS = 5  # bloqueios/limites seguidos numa plataforma antes de parar de insistir nela


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
    seguidas = 0
    for v in lista:
        if seguidas >= LIMITES_SEGUIDOS:  # a plataforma fechou a porta: não insiste, marca o resto como "?"
            info["resultados"][v["variante"]] = "INCONCLUSIVO"
            continue
        estado = checar(site, v["variante"], rede)
        info["resultados"][v["variante"]] = estado
        seguidas = seguidas + 1 if estado == "INCONCLUSIVO" else 0
        if seguidas >= LIMITES_SEGUIDOS:
            info["motivo"] = f"parou depois de {LIMITES_SEGUIDOS} bloqueios seguidos; o restante ficou como '?'"
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
                aviso = f"   (! {info['motivo']})" if info["motivo"] else ""
                mostrar(f"  {nome:<14} {len(achados)} sósia(s)   {lista_txt}{aviso}")
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


def agora_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ler_pagina(site, usuario, rede=baixar, nome_site=""):
    """
    Abre a página pública do perfil. Devolve (perfil, prova).
    perfil = {"nome", "bio"} ou None (login, bloqueio, sem etiquetas).
    prova = {"url", "status", "coletado_em_utc", "sha256", "corpo"} da resposta recebida (ou None se a rede falhou):
    é a evidência que vai para a pasta evidencias/ com o hash no manifesto.
    """
    url = site["url"].replace("{}", usuario)
    status, corpo = rede(url, site.get("headers"), True)
    prova = None
    if status is not None:
        prova = {"url": url, "status": status, "coletado_em_utc": agora_utc(),
                 "sha256": hashlib.sha256((corpo or "").encode("utf-8")).hexdigest(), "corpo": corpo or ""}
    if status != 200:
        return None, prova
    perfil = extrair_perfil(corpo)
    # página de login costuma ter só o nome da plataforma como título
    dominio = re.search(r"//(?:www\.)?([^./{]+)", site["url"])
    genericos = {normalizar(nome_site), dominio.group(1).lower() if dominio else "", "login", "entrar", "signin"}
    if normalizar(perfil["nome"]) in genericos:
        perfil["nome"] = ""
    return (perfil if (perfil["nome"] or perfil["bio"]) else None), prova


def ler_perfil(site, usuario, rede=baixar, nome_site=""):
    """Abre a página pública do perfil. None se não deu para ler (login, bloqueio, sem etiquetas)."""
    return ler_pagina(site, usuario, rede, nome_site)[0]


# ---------------------------------------------------------------------------
# 3b. Pivôs: contatos publicados nas bios (WhatsApp, telefone, e-mail, PIX, Telegram, links)
# ---------------------------------------------------------------------------
# Golpe de atendimento falso precisa levar a vítima para um canal do golpista. Esse canal
# (o número do WhatsApp, a chave PIX, o link) costuma ser o mesmo em vários perfis sósias,
# em plataformas diferentes: é a "impressão digital" da operação. CPF não é extraído (LGPD).

_RE_WA = re.compile(r"(?:wa\.me/|whatsapp\.com/send\?phone=)\+?(\d{10,15})", re.I)
_RE_FONE_BR = re.compile(r"(?<![\d/])(?:\+?55[\s.-]*)?\(?([1-9]\d)\)?[\s.-]*(9[\s.-]?\d{4})[\s.-]?(\d{4})(?!\d)")
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_RE_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_RE_CNPJ = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")
_RE_TG = re.compile(r"(?:t\.me|telegram\.me)/@?([A-Za-z0-9_]{5,32})", re.I)
_RE_LINK = re.compile(
    r"(?<![@\w.])((?:[a-z0-9-]+\.)+(?:com|net|org|br|io|me|ly|ee|ai|co|cc|gd|site|app|xyz|online|shop|store|"
    r"link|bio|info|top|click|live|vip))(/[^\s\"'<>()]*)?", re.I)
# encurtadores e páginas de links: o caminho é o que identifica (bit.ly/abc ≠ bit.ly/xyz)
ENCURTADORES = {"bit.ly", "tinyurl.com", "linktr.ee", "cutt.ly", "is.gd", "beacons.ai", "wa.link",
                "encurtador.com.br", "abre.ai", "l.ead.me", "linkme.bio"}
# domínios das próprias plataformas e dos canais já extraídos acima não contam como "link"
DOMINIOS_IGNORADOS = {"wa.me", "t.me", "telegram.me", "whatsapp.com", "api.whatsapp.com", "instagram.com",
                      "tiktok.com", "youtube.com", "youtu.be", "github.com", "gitlab.com", "twitch.tv",
                      "kick.com", "bsky.app", "medium.com", "keybase.io", "facebook.com", "x.com", "twitter.com"}
TIPOS_CONTATO = {"telefone": "telefone/WhatsApp", "email": "e-mail", "pix": "chave PIX aleatória",
                 "cnpj": "CNPJ", "telegram": "Telegram", "link": "link"}


def extrair_contatos(texto):
    """Contatos publicados em um texto: [{"tipo", "valor"}] normalizados e sem repetição."""
    texto = texto or ""
    achados, vistos = [], set()

    def add(tipo, valor):
        if valor and (tipo, valor) not in vistos:
            vistos.add((tipo, valor))
            achados.append({"tipo": tipo, "valor": valor})

    for m in _RE_WA.finditer(texto):
        add("telefone", "+" + m.group(1))
    for m in _RE_FONE_BR.finditer(texto):
        add("telefone", "+55" + m.group(1) + re.sub(r"\D", "", m.group(2)) + m.group(3))
    for m in _RE_EMAIL.finditer(texto):
        add("email", m.group(0).lower())
    for m in _RE_UUID.finditer(texto):
        add("pix", m.group(0).lower())
    for m in _RE_CNPJ.finditer(texto):
        add("cnpj", m.group(0))
    for m in _RE_TG.finditer(texto):
        add("telegram", "@" + m.group(1).lower())
    for m in _RE_LINK.finditer(texto):
        dominio = m.group(1).lower()
        dominio = dominio[4:] if dominio.startswith("www.") else dominio
        if dominio in DOMINIOS_IGNORADOS or any(dominio.endswith("." + d) for d in DOMINIOS_IGNORADOS):
            continue
        caminho = (m.group(2) or "").rstrip(".,;:!?")
        add("link", dominio + caminho if dominio in ENCURTADORES and caminho not in ("", "/") else dominio)
    return achados


def pivos_de(achados):
    """Contatos que aparecem em 2 ou mais perfis sósias: [{"tipo","valor","perfis":[(variante, site, risco)]}]."""
    grupos = {}
    for a in achados:
        for c in a.get("contatos", []):
            grupos.setdefault((c["tipo"], c["valor"]), {})[(a["variante"], a["site"])] = a["risco"]
    saida = [{"tipo": t, "valor": v, "perfis": [[var, s, r] for (var, s), r in sorted(p.items())]}
             for (t, v), p in grupos.items() if len(p) >= 2]
    return sorted(saida, key=lambda g: (-len(g["perfis"]), g["tipo"], g["valor"]))


def ligar_contatos(achados, oficiais=()):
    """
    Marca nos achados os contatos repetidos entre sósias e sobe para CRÍTICO quem divide um
    contato com um perfil CRÍTICO (mesma operação). Contatos que o próprio original publica
    são oficiais e não contam. Devolve a lista de pivôs.
    """
    oficiais = {(c["tipo"], c["valor"]) for c in oficiais}
    for a in achados:
        a["contatos"] = [c for c in a.get("contatos", []) if (c["tipo"], c["valor"]) not in oficiais]
    pivos = pivos_de(achados)
    por_perfil = {(a["variante"], a["site"]): a for a in achados}
    for g in pivos:
        membros = [por_perfil[(v, s)] for v, s, _ in g["perfis"]]
        tem_critico = any(m["risco"] == "CRÍTICO" for m in membros)
        for m in membros:
            outros = len(membros) - 1
            quem = "outro sósia" if outros == 1 else f"outros {outros} sósias"
            m["sinais"].append(f"mesmo {TIPOS_CONTATO[g['tipo']]} de {quem}: {g['valor']}")
            if tem_critico and m["risco"] != "CRÍTICO":
                m["risco"], m["peso"] = "CRÍTICO", 1.1
                m["sinais"].append("divide contato com um perfil CRÍTICO (mesma operação)")
    return pivos_de(achados)


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
    oficiais = [c for p in originais.values() if p for c in extrair_contatos(p["nome"] + " " + p["bio"])]
    legiveis = 0
    for a in achados:
        perfil, prova = (ler_pagina(sites[a["site"]], a["variante"], rede, a["site"])
                         if a["site"] in sites else (None, None))
        time.sleep(pausa)
        sinais, critico = avaliar_perfil(original, originais.get(a["site"]), perfil)
        a["perfil_nome"] = perfil["nome"] if perfil else ""
        a["perfil_bio"] = perfil["bio"] if perfil else ""
        a["perfil_legivel"] = bool(perfil)
        a["sinais"] = sinais
        a["contatos"] = extrair_contatos(a["perfil_nome"] + " " + a["perfil_bio"]) if perfil else []
        if prova:
            a["prova"] = {k: v for k, v in prova.items() if k != "corpo"}
            if prova["status"] == 200:
                a["_corpo"] = prova["corpo"]  # vai para evidencias/ em salvar() e sai do JSON
        legiveis += bool(perfil)
        if critico:
            a["risco"], a["peso"] = "CRÍTICO", 1.1
    pivos = ligar_contatos(achados, oficiais)
    criticos = sum(1 for a in achados if a["risco"] == "CRÍTICO")
    mostrar(f"\n  Perfis lidos: {legiveis} de {len(achados)} · CRÍTICOS (imitam o original): {criticos}")
    if pivos:
        mostrar(f"  Pivôs: {len(pivos)} contato(s) repetido(s) em mais de um sósia (provável mesma operação)")
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
# 4b. O fluxo completo (linha de comando e OsintbrFLOW usam esta mesma função)
# ---------------------------------------------------------------------------

def limpar_nome(nome):
    """'@Banco.Aurora ' -> 'banco.aurora'."""
    return (nome or "").strip().lstrip("@").strip().lower()


def lista_de(original, maximo=60, oficiais=()):
    """As variantes a verificar, sem as contas oficiais da marca e sem perder o limite."""
    fora = {limpar_nome(o) for o in oficiais}
    return [v for v in variantes(original, maximo + len(fora)) if v["variante"] not in fora][:maximo]


def executar(original, sites, rede=baixar, pausa=0.3, maximo=60, ler_perfis=True, oficiais=(),
             anterior=None, mostrar=None):
    """
    Busca completa de uma marca. Devolve um dicionário com:
    lista (variantes verificadas), varredura (por plataforma), achados, pivos e comparacao.
    oficiais: usernames que pertencem à própria marca (contas reserva, regionais): nunca viram sósia.
    """
    mostrar = mostrar or print
    original = limpar_nome(original)
    oficiais = {limpar_nome(o) for o in oficiais if limpar_nome(o)} - {original}
    lista = lista_de(original, maximo, oficiais)
    varredura = varrer(original, lista, sites, rede, pausa, mostrar=mostrar)
    achados = achados_de(original, lista, varredura)
    if ler_perfis:
        achados = analisar_perfis(original, achados, sites, varredura, rede, pausa, mostrar=mostrar)
    comparacao = comparar(anterior, achados, varredura)
    if comparacao:
        mostrar(f"  Desde {data_br(comparacao['desde_utc'])}: {comparacao['novos']} novo(s), "
                f"{len(comparacao['sumiram'])} sumiu(ram)")
    return {"original": original, "oficiais": sorted(oficiais), "lista": lista, "varredura": varredura,
            "achados": achados, "pivos": pivos_de(achados), "comparacao": comparacao}


def alertas_de(achados, comparacao):
    """
    O que merece alerta para quem roda agendado: sósias CRÍTICO/ALTO novos desde a busca anterior
    (ou todos os CRÍTICOS, na primeira busca da marca).
    """
    if comparacao is None:
        return [a for a in achados if a["risco"] == "CRÍTICO"]
    return [a for a in achados if a.get("novo") and a["risco"] in ("CRÍTICO", "ALTO")]


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
                                "sinais": [], "novo": False, "contatos": [], "prova": None})
    return sorted(achados, key=lambda a: (-a["peso"], a["variante"], a["site"]))


def sha256(caminho):
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def salvar(original, lista, varredura, pasta_base, fonte_sites, achados=None, comparacao=None, oficiais=()):
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
            "fonte_sites": fonte_sites, "modo": "verificação" if varredura else "só geração",
            "oficiais": list(oficiais)}

    arquivos = {}
    # evidências: a página exatamente como chegou, com extensão .txt para nunca rodar script de golpista
    com_corpo = [a for a in achados if "_corpo" in a]
    if com_corpo:
        os.makedirs(os.path.join(pasta, "evidencias"))
    for i, a in enumerate(com_corpo, 1):
        nome = f"evidencias/{i:02d}_{_seguro(a['site'])}_{_seguro(a['variante'])}.html.txt"
        arquivos[nome] = os.path.join(pasta, *nome.split("/"))
        with open(arquivos[nome], "w", encoding="utf-8", newline="") as f:
            f.write(a.pop("_corpo"))
        if a.get("prova"):
            a["prova"]["arquivo"] = nome
    pivos = pivos_de(achados)
    arquivos["variantes.txt"] = os.path.join(pasta, "variantes.txt")
    with open(arquivos["variantes.txt"], "w", encoding="utf-8") as f:
        f.write("\n".join(v["variante"] for v in lista) + "\n")
    arquivos["dados.json"] = os.path.join(pasta, "dados.json")
    with open(arquivos["dados.json"], "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "variantes": lista, "varredura": varredura, "achados": achados,
                   "pivos": pivos, "comparacao": comparacao}, f, ensure_ascii=False, indent=2)
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
    if any(a.get("contatos") for a in achados):
        arquivos["contatos.csv"] = os.path.join(pasta, "contatos.csv")
        repetidos = {(g["tipo"], g["valor"]): len(g["perfis"]) for g in pivos}
        with open(arquivos["contatos.csv"], "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["tipo", "valor", "perfis_com_este_contato", "risco", "variante", "site", "url"])
            linhas = [(c, a) for a in achados for c in a.get("contatos", [])]
            for c, a in sorted(linhas, key=lambda x: (-repetidos.get((x[0]["tipo"], x[0]["valor"]), 1),
                                                       x[0]["tipo"], x[0]["valor"])):
                w.writerow([TIPOS_CONTATO[c["tipo"]], c["valor"], repetidos.get((c["tipo"], c["valor"]), 1),
                            a["risco"], a["variante"], a["site"], a["url"]])
    if varredura:
        arquivos["denuncia.md"] = os.path.join(pasta, "denuncia.md")
        with open(arquivos["denuncia.md"], "w", encoding="utf-8") as f:
            f.write(denuncia_md(meta, achados, pivos))
        arquivos["achados.stix.json"] = os.path.join(pasta, "achados.stix.json")
        with open(arquivos["achados.stix.json"], "w", encoding="utf-8") as f:
            json.dump(stix_bundle(meta, achados, pivos), f, ensure_ascii=False, indent=2)

    hashes = {n: sha256(p) for n, p in arquivos.items()}
    with open(os.path.join(pasta, "manifesto.txt"), "w", encoding="utf-8") as f:
        f.write(f"{meta['ferramenta']} | {original} | {meta['gerado_em_utc']} UTC\n")
        for n, h in hashes.items():
            f.write(f"SHA-256  {h}  {n}\n")
    relatorio = os.path.join(pasta, "relatorio.html")
    with open(relatorio, "w", encoding="utf-8") as f:
        f.write(relatorio_html(meta, lista, varredura, achados, hashes, comparacao, pivos))
    return pasta, relatorio, achados


# ---------------------------------------------------------------------------
# 5b. Kit de denúncia e exportação STIX 2.1
# ---------------------------------------------------------------------------

# Canal oficial de cada plataforma para denunciar perfil que se passa por outra pessoa/marca.
# Só links conferidos; nas outras plataformas o caminho é o botão "Denunciar" do próprio perfil.
CANAIS = {
    "Instagram": "Formulário de falsificação de identidade: https://help.instagram.com/contact/636276399721841",
    "YouTube": "Política de falsificação de identidade e denúncia: https://support.google.com/youtube/answer/2801947",
    "TikTok": "No app: Denunciar > \"Fingindo ser outra pessoa\". Com marca registrada: "
              "https://www.tiktok.com/legal/report/Trademark",
    "Telegram": "Robô oficial @notoscam (https://t.me/notoscam) ou e-mail abuse@telegram.org",
    "GitHub": "Denunciar abuso: https://docs.github.com/en/communities/maintaining-your-safety-on-github/"
              "reporting-abuse-or-spam",
}
CANAL_PADRAO = "Abra o perfil e use o botão \"Denunciar\" (motivo: falsificação de identidade / golpe)"


def motivo_denuncia(a):
    """Frase do texto de denúncia montada só com o que o SÓSIA de fato encontrou."""
    sinais = " ".join(a.get("sinais", []))
    partes = [f"usa um nome quase igual ao do perfil oficial ({TECNICAS[a['tecnica']][1]})"]
    if "nome de exibição igual" in sinais:
        partes.append("exibe o mesmo nome do perfil oficial")
    elif "nome de exibição usa a marca" in sinais:
        partes.append("exibe o nome da marca")
    if "bio copiada" in sinais:
        partes.append("copia a bio do perfil oficial")
    if "oferece contato/pagamento" in sinais:
        partes.append("oferece atendimento, contato ou pagamento fora dos canais oficiais")
    if "mesmo " in sinais and " de outro" in sinais:
        partes.append("publica o mesmo contato que outros perfis falsos")
    return ", ".join(partes[:-1]) + (" e " if len(partes) > 1 else "") + partes[-1]


def denuncia_md(meta, achados, pivos):
    """Rascunho de denúncia por plataforma para os CRÍTICOS e ALTOS, com evidência e hash."""
    original = meta["original"]
    alvo = [a for a in achados if a["risco"] in ("CRÍTICO", "ALTO")]
    linhas = [f"# Kit de denúncia · @{original}", "",
              f"Gerado pelo {meta['ferramenta']} em {meta['gerado_em_utc']} UTC. "
              "**Abra cada perfil e confirme antes de enviar.** Registrado não quer dizer golpe; "
              "denuncie só quem se passa pela marca ou pela pessoa.", "",
              "Anexe à denúncia o print do perfil, este arquivo e o `manifesto.txt` (os SHA-256 provam que as "
              "evidências não foram alteradas depois da coleta). Golpe com prejuízo: registre também boletim de "
              "ocorrência na delegacia online do seu estado.", ""]
    if not alvo:
        linhas.append("Nenhum sósia CRÍTICO ou ALTO nesta busca. Nada a denunciar agora.")
        return "\n".join(linhas) + "\n"
    if pivos:
        linhas += ["## Contatos que ligam os perfis", "",
                   "O mesmo contato em perfis diferentes indica uma única operação. Cite isso na denúncia.", ""]
        for g in pivos:
            perfis = ", ".join(f"@{v} ({s})" for v, s, _ in g["perfis"])
            linhas.append(f"- **{TIPOS_CONTATO[g['tipo']]} `{g['valor']}`**: {perfis}")
        linhas.append("")
    for site in sorted({a["site"] for a in alvo}):
        linhas += [f"## {site}", "", f"Canal: {CANAIS.get(site, CANAL_PADRAO)}", ""]
        for a in (x for x in alvo if x["site"] == site):
            linhas += [f"### @{a['variante']} · {a['risco']}", "",
                       f"- Perfil: {a['url']}",
                       f"- Técnica: {TECNICAS[a['tecnica']][1]}"]
            if a.get("perfil_nome") or a.get("perfil_bio"):
                linhas.append(f"- Nome exibido: {a.get('perfil_nome') or '(vazio)'} · Bio: {a.get('perfil_bio') or '(vazia)'}")
            for s in a.get("sinais", []):
                linhas.append(f"- Sinal: {s}")
            p = a.get("prova")
            if p:
                linhas.append(f"- Evidência: `{p.get('arquivo', '')}` · coletada em {p['coletado_em_utc']} UTC · "
                              f"HTTP {p['status']} · SHA-256 `{p['sha256']}`")
            motivo = motivo_denuncia(a)
            linhas += ["", "Texto sugerido:", "",
                       f"> O perfil @{a['variante']} ({a['url']}) está se passando por @{original}, perfil oficial "
                       f"desta marca/pessoa. Ele {motivo}. Peço a remoção por falsificação de identidade. "
                       f"Evidência coletada em {(p or {}).get('coletado_em_utc', meta['gerado_em_utc'])} UTC.", ""]
    return "\n".join(linhas) + "\n"


_NS_SCO = "00abedb4-aa42-466c-9c01-fed23315a9b7"  # namespace UUIDv5 das STIX Cyber-observables (2.1)


def _sco_id(tipo, props):
    canon = json.dumps(props, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{tipo}--{uuid.uuid5(uuid.UUID(_NS_SCO), canon)}"


def _sdo_id(tipo, chave):
    return f"{tipo}--{uuid.uuid5(uuid.NAMESPACE_URL, 'sosia:' + chave)}"


def stix_bundle(meta, achados, pivos):
    """
    Pacote STIX 2.1 para OpenCTI, MISP e afins: o original como identidade, cada sósia como
    user-account, relação 'impersonates', nota com os sinais e um agrupamento da busca.
    IDs determinísticos: a mesma conta gera o mesmo ID em buscas diferentes (deduplica no destino).
    """
    quando = meta["gerado_em_utc"].replace(" ", "T") + ".000Z"
    ferramenta = {"type": "identity", "spec_version": "2.1", "id": _sdo_id("identity", "ferramenta"),
                  "created": quando, "modified": quando, "name": "SÓSIA", "identity_class": "system"}
    alvo = {"type": "identity", "spec_version": "2.1", "id": _sdo_id("identity", "alvo:" + meta["original"]),
            "created": quando, "modified": quando, "name": "@" + meta["original"],
            "identity_class": "organization", "created_by_ref": ferramenta["id"]}
    objetos, refs = [ferramenta, alvo], [alvo["id"]]
    comum = {"spec_version": "2.1", "created": quando, "modified": quando, "created_by_ref": ferramenta["id"]}
    for a in achados:
        tipo_conta = a["site"].lower()
        conta = {"type": "user-account", "spec_version": "2.1",
                 "id": _sco_id("user-account", {"account_login": a["variante"], "account_type": tipo_conta}),
                 "account_login": a["variante"], "account_type": tipo_conta,
                 "x_sosia_risco": a["risco"], "x_sosia_tecnica": a["tecnica"], "x_sosia_url": a["url"]}
        if a.get("perfil_nome"):
            conta["display_name"] = a["perfil_nome"]
        objetos.append(conta)
        refs.append(conta["id"])
        objetos.append({"type": "relationship", **comum,
                        "id": _sdo_id("relationship", f"{a['site']}:{a['variante']}:{meta['original']}"),
                        "relationship_type": "impersonates", "source_ref": conta["id"], "target_ref": alvo["id"],
                        "description": f"{TECNICAS[a['tecnica']][1]} · risco {a['risco']}",
                        "confidence": {"CRÍTICO": 85, "ALTO": 50, "MÉDIO": 30, "BAIXO": 15}[a["risco"]]})
        if a.get("sinais") or a.get("prova"):
            texto = "\n".join(a.get("sinais", []))
            if a.get("prova"):
                p = a["prova"]
                texto += f"\nEvidência {p.get('arquivo', '')} · {p['coletado_em_utc']} UTC · SHA-256 {p['sha256']}"
            objetos.append({"type": "note", **comum,
                            "id": _sdo_id("note", f"{a['site']}:{a['variante']}:{meta['gerado_em_utc']}"),
                            "abstract": f"SÓSIA: @{a['variante']} em {a['site']} ({a['risco']})",
                            "content": texto.strip(), "object_refs": [conta["id"]]})
    for g in pivos:
        if g["tipo"] == "email":
            obs = {"type": "email-addr", "spec_version": "2.1", "value": g["valor"],
                   "id": _sco_id("email-addr", {"value": g["valor"]})}
        elif g["tipo"] == "link":
            valor = g["valor"] if "://" in g["valor"] else "https://" + g["valor"]
            obs = {"type": "url", "spec_version": "2.1", "value": valor, "id": _sco_id("url", {"value": valor})}
        else:
            obs = None
        contas = [_sco_id("user-account", {"account_login": v, "account_type": s.lower()}) for v, s, _ in g["perfis"]]
        if obs:
            objetos.append(obs)
            refs.append(obs["id"])
        objetos.append({"type": "note", **comum, "id": _sdo_id("note", f"pivo:{g['tipo']}:{g['valor']}:{quando}"),
                        "abstract": f"Contato compartilhado: {TIPOS_CONTATO[g['tipo']]} {g['valor']}",
                        "content": f"O mesmo {TIPOS_CONTATO[g['tipo']]} aparece em {len(contas)} perfis sósias: "
                                   "provável mesma operação.",
                        "object_refs": contas + ([obs["id"]] if obs else [])})
    objetos.append({"type": "grouping", **comum, "id": _sdo_id("grouping", f"{meta['original']}:{quando}"),
                    "name": f"SÓSIA · perfis imitadores de @{meta['original']} · {meta['gerado_em_utc']} UTC",
                    "context": "suspicious-activity", "object_refs": refs})
    return {"type": "bundle", "id": _sdo_id("bundle", f"{meta['original']}:{quando}"), "objects": objetos}


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
    if a.get("contatos"):
        partes.append('<span class="contatos">' + " ".join(
            f'<span class="ct" title="{TIPOS_CONTATO[c["tipo"]]}">{html.escape(c["valor"])}</span>'
            for c in a["contatos"]) + "</span>")
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


def bloco_pivos(pivos):
    if not pivos:
        return ""
    itens = []
    for g in pivos:
        perfis = " ".join(f'<span class="selo {CLASSE_RISCO[r]}">{r}</span> <span class="mono">@{html.escape(v)}</span> '
                          f'<span class="vazio">{html.escape(s)}</span>' for v, s, r in g["perfis"])
        itens.append(f'<li><b>{TIPOS_CONTATO[g["tipo"]]}</b> <span class="mono ct">{html.escape(g["valor"])}</span>'
                     f'<div class="perfis">{perfis}</div></li>')
    return ('<h2>Pivôs: o mesmo contato em vários perfis</h2><div class="painel"><ul class="pivos">'
            + "".join(itens) + '</ul></div><p class="sub">Quem aplica o golpe precisa levar a vítima até um canal '
            'dele: o WhatsApp, a chave PIX, o link. Quando esse canal se repete em perfis diferentes, é provável que '
            'seja a mesma operação. Perfis que dividem um contato com um CRÍTICO também viram CRÍTICO. Contatos que '
            'o próprio perfil oficial publica não contam. Lista completa em <b>contatos.csv</b>.</p>')


def relatorio_html(meta, lista, varredura, achados, hashes, comparacao=None, pivos=None):
    original = meta["original"]
    confiaveis = [i for i in varredura if i["confiavel"]]
    descartados = [f'{i["site"]} ({i.get("motivo", "")})' for i in varredura if not i["confiavel"]]
    descartadas_txt = f" · descartadas: {html.escape('; '.join(descartados))}" if descartados else ""
    parciais = [f'{i["site"]} ({i["motivo"]})' for i in varredura if i["confiavel"] and i.get("motivo")]
    descartadas_txt += f" · incompletas: {html.escape('; '.join(parciais))}" if parciais else ""
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
.contatos {{ display:block; margin-top:4px }}
.ct {{ font:12px ui-monospace, Menlo, Consolas, monospace; background:color-mix(in srgb, var(--novo) 12%, transparent);
  border-radius:4px; padding:1px 5px; margin-right:4px; white-space:nowrap }}
ul.pivos {{ margin:0; padding:0; list-style:none }} ul.pivos li {{ padding:8px 0; border-bottom:1px solid var(--linha) }}
ul.pivos li:last-child {{ border-bottom:none }} .perfis {{ margin-top:4px; display:flex; flex-wrap:wrap; gap:4px 12px; font-size:13px }}
.arquivos {{ columns:2 240px; padding-left:18px }} .arquivos li {{ break-inside:avoid }}
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
  <div class="card"><b>{len(pivos or [])}</b><span>contatos repetidos entre sósias (pivôs)</span></div>
  <div class="card"><b>{len(achados)}</b><span>registros de variantes no total</span></div>
</div>

{bloco_mudancas(comparacao, achados) if varredura else ''}

{bloco_pivos(pivos)}

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

<h2>Arquivos desta busca</h2>
<ul class="arquivos sub">
<li><b>denuncia.md</b>: rascunho de denúncia por plataforma, com canal oficial, texto e evidências</li>
<li><b>achados.csv</b>: sósias encontrados (abre no Excel)</li>
<li><b>contatos.csv</b>: telefones, e-mails, PIX e links das bios (quando houver)</li>
<li><b>mudancas.csv</b>: NOVO e SUMIU desde a busca anterior (quando houver)</li>
<li><b>evidencias/</b>: cada página lida, como chegou, em .txt (não executa nada)</li>
<li><b>achados.stix.json</b>: para importar no OpenCTI, MISP ou outra plataforma de inteligência</li>
<li><b>variantes.txt</b> e <b>dados.json</b>: lista completa e dados brutos</li>
<li><b>manifesto.txt</b>: SHA-256 de tudo acima, para provar que nada foi alterado</li>
</ul>

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

SAIDA_OK, SAIDA_ERRO, SAIDA_ALERTA = 0, 1, 2


def _lista_virgulas(texto):
    return [x.strip() for x in (texto or "").split(",") if x.strip()]


def _maximo(texto):
    n = int(texto)
    if not 1 <= n <= 500:
        raise ValueError
    return n


_maximo.__name__ = "número de 1 a 500"  # aparece na mensagem de erro do argparse


def criar_parser():
    import argparse

    class Parser(argparse.ArgumentParser):
        def error(self, message):  # código 1, para não confundir erro de uso com alerta (2)
            self.print_usage(sys.stderr)
            self.exit(SAIDA_ERRO, f"sosia.py: erro: {message}\n")

    p = Parser(
        prog="sosia.py", formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False,
        description=f"SÓSIA {VERSAO}: radar de perfis imitadores (variantes de um username já registradas).",
        epilog="Exemplos:\n"
               "  python sosia.py                         modo guiado (o mesmo dos dois cliques)\n"
               "  python sosia.py --demo                  caso de demonstração, sem internet\n"
               "  python sosia.py bancoaurora             busca completa\n"
               "  python sosia.py bancoaurora --oficiais bancoaurora_sac,bancoaurora.rj\n"
               "  python sosia.py bancoaurora --extra --plataformas Instagram,Twitter,TikTok\n"
               "  python sosia.py bancoaurora --sem-abrir --alerta   (agendado: sai com código 2 se houver alerta)\n\n"
               "Códigos de saída: 0 ok · 1 erro de uso · 2 alerta (só com --alerta).")
    p._positionals.title, p._optionals.title = "argumentos", "opções"
    p.add_argument("-h", "--help", action="help", help="mostra esta ajuda e sai")
    p.add_argument("nome", nargs="?", help="username a proteger (com ou sem @)")
    p.add_argument("--demo", action="store_true", help="roda o caso fictício bancoaurora, sem internet")
    p.add_argument("--so-gerar", action="store_true", help="só gera a lista de variantes, sem acessar nada")
    p.add_argument("--sem-perfil", action="store_true", help="não abre os perfis encontrados (sem nível CRÍTICO)")
    p.add_argument("--max", type=_maximo, default=60, metavar="N", help="variantes a verificar, de 1 a 500 (padrão: 60)")
    p.add_argument("--oficiais", type=_lista_virgulas, default=[], metavar="A,B",
                   help="contas da própria marca, separadas por vírgula: nunca viram sósia")
    p.add_argument("--plataformas", type=_lista_virgulas, default=[], metavar="A,B",
                   help="só estas plataformas (ex.: Instagram,TikTok)")
    p.add_argument("--extra", action="store_true", help="inclui X (Twitter), Pinterest, Reddit, Snapchat e Patreon")
    p.add_argument("--sites", metavar="ARQUIVO", help="outra lista de sites (ex.: data.json do Sherlock)")
    p.add_argument("--saida", metavar="PASTA", help="onde salvar (padrão: ./resultados)")
    p.add_argument("--sem-abrir", action="store_true", help="não abre o relatório no navegador")
    p.add_argument("--alerta", action="store_true",
                   help="sai com código 2 se houver CRÍTICO/ALTO novo (ou CRÍTICO na 1ª busca)")
    p.add_argument("--versao", action="version", version=VERSAO, help="mostra a versão e sai")
    return p


def _entrada(pergunta):
    """input() que não quebra sem teclado (agendador, pipe vazio): devolve ""."""
    try:
        return input(pergunta)
    except EOFError:
        print()
        return ""


def _guiado():
    print(f"\nSÓSIA {VERSAO} — radar de perfis imitadores\n")
    nome = _entrada("Username da marca ou pessoa a proteger (ou DEMO para o exemplo): ").strip()
    if nome.upper() == "DEMO":
        return ["--demo"]
    if not limpar_nome(nome):
        return []
    args = [nome]
    oficiais = _entrada("Outras contas oficiais da marca, separadas por vírgula (Enter se não houver): ").strip()
    if oficiais:
        args += ["--oficiais", oficiais]
    if _entrada("Só gerar a lista, sem acessar as plataformas? [s/N]: ").strip().lower().startswith("s"):
        args.append("--so-gerar")
    return args


def main(argv):
    guiado = len(argv) == 0
    if guiado:
        argv = _guiado()
        if not argv:
            print("Nenhum nome digitado. Rode de novo e digite o username (ou DEMO).")
            _entrada("\nPressione Enter para sair.")
            return SAIDA_ERRO
    parser = criar_parser()
    a = parser.parse_args(argv)
    if not a.demo and not limpar_nome(a.nome):
        parser.print_usage()
        print("sosia.py: falta o username a proteger (ou use --demo).")
        return SAIDA_ERRO
    try:
        sites = carregar_sites(a.sites, a.extra, a.plataformas)
    except (OSError, ValueError) as e:
        print(f"sosia.py: {e}")
        return SAIDA_ERRO
    rotulo = (os.path.basename(a.sites) if a.sites else "sites_padrao.json (Sherlock, subconjunto)") + \
        (" + sites_extra.json" if a.extra else "")
    pasta_base = a.saida or os.path.join(os.getcwd(), "resultados")
    rede, pausa, original, anterior = baixar, 0.3, limpar_nome(a.nome), None
    if a.demo:
        original, rede, anterior = rede_demo(sites)
        pausa = 0
    elif not a.so_gerar:
        anterior = execucao_anterior(pasta_base, original)

    alvo = "só geração" if a.so_gerar else f"{len(sites)} plataformas"
    oficiais = sorted({limpar_nome(o) for o in a.oficiais if limpar_nome(o)} - {original})
    lista = lista_de(original, a.max, oficiais)
    print(f"\nSÓSIA :: {original} :: {len(lista)} variantes :: {alvo}{' :: DEMONSTRAÇÃO' if a.demo else ''}\n")
    if a.so_gerar:
        busca = {"lista": lista, "varredura": [], "achados": [], "comparacao": None, "oficiais": oficiais}
    else:
        busca = executar(original, sites, rede, pausa, a.max, not a.sem_perfil, oficiais, anterior)
    pasta, relatorio, achados = salvar(original, busca["lista"], busca["varredura"], pasta_base, rotulo,
                                      busca["achados"], busca["comparacao"], busca["oficiais"])

    conta = {r: sum(1 for x in achados if x["risco"] == r) for r in ("CRÍTICO", "ALTO")}
    print(f"\nSósias registrados: {len(achados)} (CRÍTICO: {conta['CRÍTICO']}, ALTO: {conta['ALTO']})")
    pivos = pivos_de(achados)
    if pivos:
        print(f"Pivôs (mesmo contato em vários sósias): {len(pivos)}")
    print(f"Relatório: {relatorio}")
    if busca["varredura"]:
        print(f"Kit de denúncia: {os.path.join(pasta, 'denuncia.md')}")
    codigo = SAIDA_OK
    if a.alerta and busca["varredura"]:
        alertas = alertas_de(achados, busca["comparacao"])
        if alertas:
            print(f"ALERTA: {len(alertas)} sósia(s) para olhar agora: "
                  + ", ".join(f"{x['variante']} ({x['site']}, {x['risco']})" for x in alertas[:5])
                  + (" ..." if len(alertas) > 5 else ""))
            codigo = SAIDA_ALERTA
    if not a.sem_abrir:
        webbrowser.open("file://" + os.path.abspath(relatorio))
    if guiado:
        _entrada("\nPressione Enter para sair.")
    return codigo


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nInterrompido. Nada da busca em andamento foi salvo.")
        sys.exit(130)
