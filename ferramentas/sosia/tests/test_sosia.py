"""Testes do SÓSIA. Rodam sem internet: python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import sosia  # noqa: E402


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


SITE = {"url": "https://ex.com/{}", "errorType": "status_code"}
SITE_MSG = {"url": "https://m.com/{}", "errorType": "message", "errorMsg": "nao existe"}


class TestVariantes(unittest.TestCase):
    def nomes(self, original, maximo=500):
        return {v["variante"]: v["tecnica"] for v in sosia.variantes(original, maximo)}

    def test_tecnicas_basicas(self):
        n = self.nomes("bancoaurora")
        self.assertEqual(n["banc0aurora"], "homoglifo")
        self.assertEqual(n["bancoaurora_oficial"], "isca")
        self.assertEqual(n["banco_aurora"], "separador")
        self.assertEqual(n["bancoauroraa"], "duplicacao")
        self.assertEqual(n["bancoaurra"], "omissao")
        self.assertEqual(n["bancoaruora"], "troca")

    def test_homoglifos_de_duas_letras(self):
        n = self.nomes("modem")
        self.assertIn("rnodem", n)
        self.assertIn("moclem", n)
        self.assertIn("modern", n)  # o clássico m → rn
        self.assertIn("worm", self.nomes("vvorm"))

    def test_separadores_existentes(self):
        n = self.nomes("ana.silva")
        self.assertIn("anasilva", n)
        self.assertIn("ana_silva", n)
        self.assertIn("ana-silva", n)

    def test_sem_repeticao_e_sem_original(self):
        lista = [v["variante"] for v in sosia.variantes("Ana_Silva", 500)]
        self.assertEqual(len(lista), len(set(lista)))
        self.assertNotIn("ana_silva", lista)

    def test_limite_e_prioridade(self):
        lista = sosia.variantes("bancoaurora", 20)
        self.assertEqual(len(lista), 20)
        self.assertEqual(lista[0]["tecnica"], "homoglifo")
        pesos = [v["peso"] for v in lista[:10]]
        self.assertTrue(all(p >= 0.95 for p in pesos))

    def test_rodizio_mantem_variedade(self):
        tecnicas = {v["tecnica"] for v in sosia.variantes("bancoaurora", 60)}
        self.assertEqual(tecnicas, set(sosia.TECNICAS))

    def test_destaque(self):
        self.assertEqual(sosia.destacar("banco", "banc0"), "banc<mark>0</mark>")
        self.assertIn("<mark>_oficial</mark>", sosia.destacar("x", "x_oficial"))


class TestChecagem(unittest.TestCase):
    def test_semantica_sherlock(self):
        c = sosia.checar
        self.assertEqual(c(SITE, "a", lambda *a: (200, "")), "EXISTE")
        self.assertEqual(c(SITE, "a", lambda *a: (404, "")), "NAO_EXISTE")
        self.assertEqual(c(SITE, "a", lambda *a: (429, "")), "INCONCLUSIVO")
        self.assertEqual(c(SITE, "a", lambda *a: (None, "erro")), "INCONCLUSIVO")
        self.assertEqual(c(SITE_MSG, "a", lambda *a: (200, "nao existe")), "NAO_EXISTE")
        self.assertEqual(c(SITE_MSG, "a", lambda *a: (200, "perfil")), "EXISTE")
        self.assertEqual(c(dict(SITE, regexCheck="^[a-z]+$"), "a_1", lambda *a: (200, "")), "INVALIDO")

    def test_sonda_tem_prioridade(self):
        visto = []
        sosia.checar(dict(SITE, urlProbe="https://api.ex.com/{}"), "ana",
                     lambda url, *a: visto.append(url) or (404, ""))
        self.assertEqual(visto, ["https://api.ex.com/ana"])

    def test_site_que_mente_e_descartado(self):
        lista = sosia.variantes("ana", 5)
        info = sosia.varrer_site("X", SITE, "ana", lista, lambda *a: (200, ""), 0)
        self.assertFalse(info["confiavel"])
        self.assertEqual(info["resultados"], {})

    def test_site_inacessivel_e_descartado(self):
        info = sosia.varrer_site("X", SITE, "ana", sosia.variantes("ana", 5), lambda *a: (None, "x"), 0)
        self.assertFalse(info["confiavel"])
        self.assertIn("inacessível", info["motivo"])

    def test_varredura_e_achados(self):
        lista = sosia.variantes("ana", 60)
        alvo = "https://ex.com/an4"

        def rede(url, *a):
            return (200, "") if url in (alvo, "https://ex.com/ana") else (404, "")
        varredura = sosia.varrer("ana", lista, {"Ex": SITE}, rede, 0, 2, lambda *a: None)
        self.assertTrue(varredura[0]["confiavel"])
        self.assertEqual(varredura[0]["original"], "EXISTE")
        achados = sosia.achados_de("ana", lista, varredura)
        self.assertEqual([(a["variante"], a["risco"]) for a in achados], [("an4", "ALTO")])


class TestSaidas(unittest.TestCase):
    def test_lista_padrao(self):
        self.assertGreaterEqual(len(sosia.carregar_sites()), 10)

    def test_demo_ponta_a_ponta(self):
        sites = sosia.carregar_sites()
        original, rede, anterior = sosia.rede_demo(sites)
        lista = sosia.variantes(original, 60)
        varredura = sosia.varrer(original, lista, sites, rede, 0, 4, lambda *a: None)
        achados = sosia.achados_de(original, lista, varredura)
        pares = {(a["variante"], a["site"]) for a in achados}
        self.assertIn(("banc0aurora", "Instagram"), pares)
        self.assertIn(("bancoaurora_suporte", "Telegram"), pares)
        self.assertEqual(len(achados), 7)
        kick = next(i for i in varredura if i["site"] == "Kick")
        self.assertFalse(kick["confiavel"])
        achados = sosia.analisar_perfis(original, achados, sites, varredura, rede, 0, lambda *a: None)
        criticos = {(a["variante"], a["site"]) for a in achados if a["risco"] == "CRÍTICO"}
        self.assertEqual(criticos, {("banc0aurora", "Instagram"), ("bancoaurora_oficial", "Instagram"),
                                    ("bancoaurora_suporte", "Telegram")})
        self.assertEqual(achados[0]["risco"], "CRÍTICO")  # críticos sobem para o topo
        comparacao = sosia.comparar(anterior, achados, varredura)
        self.assertEqual(comparacao["novos"], 3)
        self.assertEqual(comparacao["sumiram"], [{"variante": "bancoaurora_ajuda", "site": "YouTube"}])
        with tempfile.TemporaryDirectory() as tmp:
            pasta, relatorio, _ = sosia.salvar(original, lista, varredura, tmp, "teste", achados, comparacao)
            texto = ler(relatorio)
            self.assertIn("banc<mark>0</mark>aurora", texto)
            self.assertIn("SUMIU", texto)
            manifesto = ler(os.path.join(pasta, "manifesto.txt"))
            for nome in ("variantes.txt", "dados.json", "achados.csv", "mudancas.csv"):
                self.assertIn(sosia.sha256(os.path.join(pasta, nome)), manifesto)
            self.assertEqual(len(ler(os.path.join(pasta, "variantes.txt")).split()), 60)
            self.assertEqual(ler(os.path.join(pasta, "mudancas.csv")).count("NOVO"), 3)

    def test_so_gerar_nao_acessa_rede(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.print"), \
                mock.patch("sosia.baixar", side_effect=AssertionError("rede!")):
            self.assertEqual(sosia.main(["marca", "--so-gerar", "--sem-abrir", "--saida", tmp]), 0)
            pasta = os.path.join(tmp, os.listdir(tmp)[0])
            dados = json.loads(ler(os.path.join(pasta, "dados.json")))
            self.assertEqual(dados["varredura"], [])

    def test_html_escapa(self):
        meta = {"ferramenta": "t", "original": "<i>x</i>", "gerado_em_utc": "", "variantes_verificadas": 0,
                "plataformas": 0, "fonte_sites": "<b>", "modo": ""}
        texto = sosia.relatorio_html(meta, [], [], [], {})
        self.assertNotIn("<i>x</i>", texto)

    def test_cli_demo(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.print"):
            self.assertEqual(sosia.main(["--demo", "--sem-abrir", "--saida", tmp]), 0)


class TestCombinada(unittest.TestCase):
    def test_homoglifo_mais_isca(self):
        n = {v["variante"]: v["tecnica"] for v in sosia.variantes("bancoaurora", 500)}
        self.assertEqual(n["banc0aurora_suporte"], "combinada")
        self.assertEqual(n["banc0aurora_oficial"], "combinada")

    def test_combinada_entra_no_padrao_e_e_alto(self):
        lista = sosia.variantes("bancoaurora", 60)
        comb = [v for v in lista if v["tecnica"] == "combinada"]
        self.assertGreaterEqual(len(comb), 5)
        self.assertEqual(sosia.risco(comb[0]["peso"]), "ALTO")


INSTAGRAM = '<meta property="og:title" content="Banco Aurora (@bancoaurora) &bull; Instagram">' \
            '<meta content="Conta digital &amp; sem tarifas" property="og:description">'


class TestPerfil(unittest.TestCase):
    def test_extrai_nome_e_bio_nas_duas_ordens(self):
        p = sosia.extrair_perfil(INSTAGRAM)
        self.assertEqual(p["nome"], "Banco Aurora")
        self.assertEqual(p["bio"], "Conta digital & sem tarifas")

    def test_titulo_quando_nao_ha_og(self):
        self.assertEqual(sosia.extrair_perfil("<title>Ana Silva | Medium</title>")["nome"], "Ana Silva")

    def test_pagina_de_login_nao_conta_como_perfil(self):
        site = {"url": "https://www.instagram.com/{}"}
        def rede(*a):
            return (200, "<title>Instagram</title>")
        self.assertIsNone(sosia.ler_perfil(site, "x", rede, "Instagram"))
        self.assertIsNone(sosia.ler_perfil(site, "x", lambda *a: (404, ""), "Instagram"))

    def test_avaliacao(self):
        orig = {"nome": "Banco Aurora", "bio": "Conta digital sem tarifas"}
        ava = sosia.avaliar_perfil
        sinais, critico = ava("bancoaurora", orig, {"nome": "Banco  Aurora", "bio": "fotos de viagem"})
        self.assertTrue(critico)
        self.assertIn("nome de exibição igual ao do original", sinais)
        sinais, critico = ava("bancoaurora", orig, {"nome": "Suporte Banco Aurora", "bio": "Chave PIX aqui"})
        self.assertTrue(critico)
        self.assertTrue(any("pix" in s for s in sinais))
        sinais, critico = ava("bancoaurora", orig, {"nome": "Fã do Banco Aurora", "bio": "não somos o banco"})
        self.assertFalse(critico)
        self.assertEqual(sinais, ["nome de exibição usa a marca"])
        self.assertEqual(ava("bancoaurora", orig, {"nome": "Maria", "bio": "bolos caseiros"}), ([], False))
        self.assertEqual(ava("bancoaurora", orig, None), ([], False))

    def test_acento_nao_atrapalha(self):
        self.assertEqual(sosia.normalizar("Bánco Áurora!"), "bancoaurora")
        sinais, _ = sosia.avaliar_perfil("x", None, {"nome": "", "bio": "Promoção: resgate já"})
        self.assertIn("promocao", sinais[0])


class TestMonitoramento(unittest.TestCase):
    def test_sem_anterior(self):
        achados = [{"variante": "a", "site": "S"}]
        self.assertIsNone(sosia.comparar(None, achados, []))
        self.assertFalse(achados[0]["novo"])

    def test_sumiu_so_onde_foi_verificado(self):
        anterior = {"gerado_em_utc": "2026-01-01 00:00:00", "achados": [["a", "S"], ["b", "S"], ["c", "Fora"]]}
        varredura = [{"site": "S", "confiavel": True, "resultados": {"a": "EXISTE", "b": "NAO_EXISTE"}},
                     {"site": "Fora", "confiavel": False, "resultados": {}}]
        achados = [{"variante": "a", "site": "S"}, {"variante": "n", "site": "S"}]
        c = sosia.comparar(anterior, achados, varredura)
        self.assertEqual([a["novo"] for a in achados], [False, True])
        self.assertEqual(c["sumiram"], [{"variante": "b", "site": "S"}])  # "c" não foi verificado agora

    def test_acha_execucao_anterior_na_pasta(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(sosia.execucao_anterior(tmp, "marca"))
            for nome, modo in (("sosia_marca_20260101-000000", "verificação"),
                               ("sosia_marca_20260102-000000", "só geração"),
                               ("sosia_outra_20260103-000000", "verificação")):
                os.makedirs(os.path.join(tmp, nome))
                with open(os.path.join(tmp, nome, "dados.json"), "w", encoding="utf-8") as f:
                    json.dump({"meta": {"modo": modo, "gerado_em_utc": nome[-15:]},
                               "achados": [{"variante": "x", "site": "S"}]}, f)
            ant = sosia.execucao_anterior(tmp, "marca")
            self.assertEqual(ant["pasta"], "sosia_marca_20260101-000000")  # pula a 'só geração' e a outra marca
            self.assertEqual(ant["achados"], [["x", "S"]])

    def test_duas_execucoes_reais_pela_linha_de_comando(self):
        sites = sosia.carregar_sites()
        _, rede, _ = sosia.rede_demo(sites)
        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.print"), \
                mock.patch("sosia.baixar", side_effect=rede), mock.patch("sosia.time.sleep"):
            self.assertEqual(sosia.main(["bancoaurora", "--sem-abrir", "--saida", tmp]), 0)
            self.assertEqual(sosia.main(["bancoaurora", "--sem-abrir", "--saida", tmp]), 0)
            self.assertEqual(len(os.listdir(tmp)), 2)  # mesmo segundo: pastas diferentes
            ultima = sorted(os.listdir(tmp))[-1]  # "-2" vem depois na ordem alfabética
            dados = json.loads(ler(os.path.join(tmp, ultima, "dados.json")))
            self.assertEqual(dados["comparacao"]["novos"], 0)
            self.assertEqual(dados["comparacao"]["sumiram"], [])


if __name__ == "__main__":
    unittest.main()


class TestPivos(unittest.TestCase):
    """1.2: contatos publicados nas bios ligam perfis da mesma operação."""

    def tipos(self, texto):
        return {(c["tipo"], c["valor"]) for c in sosia.extrair_contatos(texto)}

    def test_whatsapp_e_telefone_viram_o_mesmo_numero(self):
        self.assertEqual(self.tipos("fale: wa.me/5531900000000"), {("telefone", "+5531900000000")})
        self.assertEqual(self.tipos("Chame no (31) 90000-0000."), {("telefone", "+5531900000000")})
        self.assertEqual(self.tipos("+55 31 9 0000-0000"), {("telefone", "+5531900000000")})
        self.assertEqual(self.tipos("api.whatsapp.com/send?phone=5511988887777"), {("telefone", "+5511988887777")})

    def test_outros_tipos(self):
        t = self.tipos("PIX 123e4567-e89b-12d3-a456-426614174000 · sac@aurora-ajuda.com · t.me/AuroraSAC · "
                       "CNPJ 12.345.678/0001-90 · bit.ly/aurora7 · https://aurora-bonus.site/resgate")
        self.assertIn(("pix", "123e4567-e89b-12d3-a456-426614174000"), t)
        self.assertIn(("email", "sac@aurora-ajuda.com"), t)
        self.assertIn(("telegram", "@aurorasac"), t)
        self.assertIn(("cnpj", "12.345.678/0001-90"), t)
        self.assertIn(("link", "bit.ly/aurora7"), t)  # encurtador: o caminho identifica
        self.assertIn(("link", "aurora-bonus.site"), t)  # site: o domínio identifica
        self.assertNotIn(("link", "aurora-ajuda.com"), t)  # domínio de e-mail não vira link

    def test_ignora_plataformas_cpf_e_texto_comum(self):
        self.assertEqual(self.tipos("veja instagram.com/x e youtube.com/@x · CPF 123.456.789-09 · "
                                    "ligue já, 100% seguro, ano 2026"), set())

    def achado(self, variante, site, risco, bio):
        return {"variante": variante, "site": site, "risco": risco, "peso": 1.1 if risco == "CRÍTICO" else 0.95,
                "sinais": [], "contatos": sosia.extrair_contatos(bio)}

    def test_contato_compartilhado_liga_e_contamina(self):
        a = self.achado("banc0aurora", "Instagram", "CRÍTICO", "wa.me/5531900000000")
        b = self.achado("aurora.sac", "TikTok", "ALTO", "WhatsApp (31) 90000-0000")
        c = self.achado("bancoaurora_br", "YouTube", "ALTO", "sem contato")
        pivos = sosia.ligar_contatos([a, b, c])
        self.assertEqual(len(pivos), 1)
        self.assertEqual(pivos[0]["valor"], "+5531900000000")
        self.assertEqual(b["risco"], "CRÍTICO")
        self.assertIn("divide contato com um perfil CRÍTICO (mesma operação)", b["sinais"])
        self.assertEqual(c["risco"], "ALTO")
        self.assertTrue(any("de outro sósia" in s for s in a["sinais"]))

    def test_contato_oficial_nao_conta(self):
        a = self.achado("a1", "Instagram", "CRÍTICO", "sac@aurora.com")
        b = self.achado("a2", "TikTok", "ALTO", "sac@aurora.com")
        pivos = sosia.ligar_contatos([a, b], oficiais=sosia.extrair_contatos("Atendimento: sac@aurora.com"))
        self.assertEqual(pivos, [])
        self.assertEqual(b["risco"], "ALTO")
        self.assertEqual(a["contatos"], [])


class TestEvidenciaDenunciaStix(unittest.TestCase):
    """1.2: página lida vira evidência com SHA-256; denúncia e STIX saem da mesma busca."""

    def rodar_demo(self, tmp):
        sites = sosia.carregar_sites()
        original, rede, anterior = sosia.rede_demo(sites)
        lista = sosia.variantes(original, 60)
        varredura = sosia.varrer(original, lista, sites, rede, 0, 4, lambda *a: None)
        achados = sosia.achados_de(original, lista, varredura)
        achados = sosia.analisar_perfis(original, achados, sites, varredura, rede, 0, lambda *a: None)
        return sosia.salvar(original, lista, varredura, tmp, "teste", achados,
                            sosia.comparar(anterior, achados, varredura))

    def test_prova_da_leitura(self):
        perfil, prova = sosia.ler_pagina(SITE, "ana", lambda *a: (200, '<meta property="og:title" content="Ana">'))
        self.assertEqual(perfil["nome"], "Ana")
        self.assertEqual(prova["status"], 200)
        self.assertEqual(len(prova["sha256"]), 64)
        self.assertEqual(sosia.ler_pagina(SITE, "ana", lambda *a: (None, "x")), (None, None))

    def test_demo_gera_pivo_evidencias_denuncia_e_stix(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta, relatorio, achados = self.rodar_demo(tmp)
            dados = json.loads(ler(os.path.join(pasta, "dados.json")))
            self.assertEqual([(p["tipo"], p["valor"]) for p in dados["pivos"]], [("telefone", "+5531900000000")])
            self.assertNotIn("_corpo", json.dumps(dados))
            # cada evidência no disco tem o mesmo hash registrado na prova e no manifesto
            manifesto = ler(os.path.join(pasta, "manifesto.txt"))
            provas = [a["prova"] for a in achados if a.get("prova", {}) and a["prova"].get("arquivo")]
            self.assertEqual(len(provas), 7)
            for p in provas:
                caminho = os.path.join(pasta, *p["arquivo"].split("/"))
                self.assertTrue(p["arquivo"].endswith(".html.txt"))
                self.assertEqual(sosia.sha256(caminho), p["sha256"])
                self.assertIn(p["sha256"] + "  " + p["arquivo"], manifesto)
            for nome in ("contatos.csv", "denuncia.md", "achados.stix.json"):
                self.assertIn(sosia.sha256(os.path.join(pasta, nome)), manifesto)
            self.assertIn("+5531900000000,2,CRÍTICO,banc0aurora", ler(os.path.join(pasta, "contatos.csv")))
            denuncia = ler(os.path.join(pasta, "denuncia.md"))
            self.assertIn("https://help.instagram.com/contact/636276399721841", denuncia)
            self.assertIn("@notoscam", denuncia)
            self.assertIn("exibe o mesmo nome do perfil oficial", denuncia)
            self.assertNotIn("@github", denuncia.lower())  # só plataformas com CRÍTICO/ALTO
            self.assertIn("Pivôs: o mesmo contato", ler(relatorio))

    def test_stix_bem_formado_e_deterministico(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta, _, _ = self.rodar_demo(tmp)
            b1 = json.loads(ler(os.path.join(pasta, "achados.stix.json")))
            pasta2, _, _ = self.rodar_demo(tmp)
            b2 = json.loads(ler(os.path.join(pasta2, "achados.stix.json")))
        tipos = [o["type"] for o in b1["objects"]]
        self.assertEqual(b1["type"], "bundle")
        self.assertEqual(tipos.count("user-account"), 7)
        self.assertEqual(tipos.count("relationship"), 7)
        self.assertEqual(tipos.count("grouping"), 1)
        ids = {o["id"] for o in b1["objects"]}
        self.assertEqual(len(ids), len(b1["objects"]))
        for o in b1["objects"]:
            for ref in o.get("object_refs", []) + [o.get("source_ref"), o.get("target_ref"), o.get("created_by_ref")]:
                if ref:
                    self.assertIn(ref, ids)  # nenhuma referência quebrada
            if o["type"] != "user-account" and o["type"] != "bundle":
                self.assertEqual(o["spec_version"], "2.1")
        # a mesma conta tem o mesmo ID em buscas diferentes (deduplica no OpenCTI/MISP)
        def contas(b):
            return {o["id"] for o in b["objects"] if o["type"] == "user-account"}
        self.assertEqual(contas(b1), contas(b2))
        # valor conferido com a biblioteca oficial stix2 (UserAccount(account_login='banc0aurora', account_type='instagram'))
        self.assertIn(sosia._sco_id("user-account", {"account_login": "banc0aurora", "account_type": "instagram"}),
                      contas(b1))
