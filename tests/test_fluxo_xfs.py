"""Regressões offline do fluxo XFS/DDownload e do setup do Colab.

python -m unittest discover -s tests -p "test_fluxo_xfs.py" -v
"""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch

from downloader_universal.config import CONFIG
from downloader_universal.hosts import xfilesharing as xfs
from downloader_universal.hosts.ddownload import DDownload
from downloader_universal.transfer import DownloadError

URL = "https://ddownload.com/h2v6slabi0bi/toni_head128_X_8bit.png"
DIRETO = "https://cdn.example.org/d/token/toni_head128_X_8bit.png"


def pagina(extra="", op="download2"):
    return (f'<form method="post"><input type="hidden" name="op" value="{op}">'
            '<input type="hidden" name="id" value="h2v6slabi0bi">'
            '<input type="hidden" name="rand" value="token-da-sessao">'
            f'{extra}<button type="submit">Download</button></form>')


def resposta(html="", status=200, headers=None):
    return Mock(text=html, status_code=status, url=URL, headers=headers or {})


class FluxoXFS(unittest.TestCase):
    def setUp(self):
        config = patch.dict(CONFIG, verbose=False, max_espera_download=180)
        config.start()
        self.addCleanup(config.stop)
        for nome in ("time.sleep", "stream_download", "_salvar_diagnostico"):
            mocker = patch(f"downloader_universal.hosts.xfilesharing.{nome}")
            setattr(self, nome.split(".")[-1], mocker.start())
            self.addCleanup(mocker.stop)
        self.stream_download.return_value = "downloads/toni_head128_X_8bit.png"
        self.sess = Mock(headers={})
        self.sess.post.return_value = resposta(status=302, headers={"Location": DIRETO})

    def baixar(self, html):
        return xfs.baixar_xfs(URL, "downloads", sess=self.sess, html_inicial=html)

    def test_formatos_de_contador(self):
        casos = [
            ('<div id="countdown">Etapa 2: <span class="seconds">60</span></div>', 60),
            ('<input value="150" id="countdown">', 150),
            ('<span id="countdown_str">20</span>', 20),
            ('<div id="countdown">Please wait <b>60</b> seconds</div>', 60),
            ('<script>var wait = 15;</script>', 15),
            ('<script>let seconds = 60;</script>', 60),
            ('<script>countdown(60);</script>', 60),
            ('<div id="countdown"><span class="seconds">240</span></div>', 240),
            ('<p>Arquivo 128.png, 9120 bytes</p>', 0),
            (None, 0),
        ]
        for html, esperado in casos:
            with self.subTest(html=html):
                self.assertEqual(xfs.countdown(html), esperado)

    def test_espera_inteira_antes_do_post_e_preserva_sessao(self):
        eventos = []
        self.sleep.side_effect = lambda segundos: eventos.append(("espera", segundos))
        self.sess.post.side_effect = lambda *a, **kw: (
            eventos.append(("post", kw["data"]["rand"]))
            or resposta(status=302, headers={"Location": DIRETO}))
        resultado = self.baixar(pagina('<script>var seconds = 150;</script>'))
        self.assertEqual(eventos, [("espera", 152), ("post", "token-da-sessao")])
        self.assertEqual(resultado, self.stream_download.return_value)
        self.stream_download.assert_called_once_with(
            DIRETO, "downloads", sess=self.sess, nome=None, referer=URL, force=False)

    def test_contador_acima_do_limite_nao_e_encurtado(self):
        with self.assertRaisesRegex(DownloadError, "contador exige 240s"):
            self.baixar(pagina('<span id="countdown">240</span>'))
        self.sess.post.assert_not_called()
        self.sleep.assert_not_called()
        self._salvar_diagnostico.assert_called_once()

    def test_duas_etapas_espera_so_na_etapa_com_contador(self):
        self.sess.post.side_effect = [
            resposta(pagina('<span id="countdown">60</span>')),
            resposta(status=302, headers={"Location": DIRETO}),
        ]
        self.baixar(pagina(op="download1"))
        self.assertEqual([c.kwargs["data"]["op"] for c in self.sess.post.call_args_list],
                         ["download1", "download2"])
        self.sleep.assert_called_once_with(62)

    def test_captcha_pendente_nao_envia_formulario(self):
        for desafio in ('<div class="cf-turnstile" data-sitekey="publica"></div>',
                        '<textarea name="g-recaptcha-response"></textarea>',
                        '<div class="h-captcha"></div>',
                        '<input name="code" type="text">'):
            with self.subTest(desafio=desafio):
                with self.assertRaisesRegex(DownloadError, "verificação por"):
                    self.baixar(pagina(desafio))
        self.sess.post.assert_not_called()
        self.sleep.assert_not_called()

    def test_script_carregado_sem_widget_nao_bloqueia_formulario(self):
        self.baixar(pagina('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>'))
        self.sess.post.assert_called_once()

    def test_resposta_de_captcha_preenchida_e_preservada(self):
        self.baixar(pagina('<div class="g-recaptcha"></div>'
                           '<textarea name="g-recaptcha-response">resposta-teste</textarea>'))
        campos = self.sess.post.call_args.kwargs["data"]
        self.assertEqual(campos["g-recaptcha-response"], "resposta-teste")

    def test_recusa_do_contador_nao_e_diagnosticada_como_captcha(self):
        self.sess.post.return_value = resposta('<div>Skipped countdown</div>')
        with self.assertRaisesRegex(DownloadError, "contagem regressiva") as erro:
            self.baixar(pagina())
        self.assertNotIn("captcha", str(erro.exception).lower())
        self.sess.post.assert_called_once()
        self._salvar_diagnostico.assert_called_once()

    def test_erros_de_captcha_sao_distintos(self):
        for texto in ("Wrong captcha", "Captcha error", "Invalid captcha"):
            with self.subTest(texto=texto):
                msg = xfs.mensagem_erro(f"<p>{texto}</p>")
                self.assertIn("captcha", msg)
                self.assertNotIn("contagem regressiva", msg)


class OrientacaoDDownload(unittest.TestCase):
    @patch("downloader_universal.hosts.ddownload.sessao")
    @patch("downloader_universal.hosts.ddownload.info_arquivo", return_value=None)
    @patch("downloader_universal.hosts.ddownload.baixar_xfs")
    def test_recusas_genericas_recebem_orientacao_sem_inventar_turnstile(self, fluxo, *_):
        with patch.dict(CONFIG, verbose=False):
            for msg in ("O site recusou o captcha.", "O site recusou a contagem regressiva."):
                fluxo.side_effect = DownloadError(msg)
                with self.assertRaises(DownloadError) as erro:
                    DDownload.baixar(URL, "downloads")
                self.assertIn("Abra o link original no navegador", str(erro.exception))
                self.assertNotIn("Turnstile", str(erro.exception))
                self.assertIn("não implementa autenticação premium", str(erro.exception))

    @patch("downloader_universal.hosts.ddownload.sessao")
    @patch("downloader_universal.hosts.ddownload.info_arquivo", return_value=None)
    @patch("downloader_universal.hosts.ddownload.baixar_xfs")
    def test_turnstile_tem_orientacao_especifica(self, fluxo, *_):
        fluxo.side_effect = DownloadError("A página exige Cloudflare Turnstile.")
        with patch.dict(CONFIG, verbose=False), self.assertRaises(DownloadError) as erro:
            DDownload.baixar(URL, "downloads")
        self.assertIn("navegador para executar a verificação", str(erro.exception))

    @patch("downloader_universal.hosts.ddownload.sessao")
    @patch("downloader_universal.hosts.ddownload.info_arquivo", return_value=None)
    @patch("downloader_universal.hosts.ddownload.baixar_xfs")
    def test_erro_de_rede_nao_recebe_diagnostico_de_captcha(self, fluxo, *_):
        fluxo.side_effect = DownloadError("Erro de rede/SSL")
        with patch.dict(CONFIG, verbose=False), self.assertRaises(DownloadError) as erro:
            DDownload.baixar(URL, "downloads")
        self.assertEqual(str(erro.exception), "Erro de rede/SSL")


class SetupColab(unittest.TestCase):
    def test_atualiza_caminho_absoluto_e_exige_reinicio_se_ja_importado(self):
        raiz = Path(__file__).resolve().parents[1]
        notebook = json.loads((raiz / "Downloader_Universal.ipynb").read_text())
        codigo = "".join(notebook["cells"][1]["source"])
        with patch("subprocess.run") as executar, patch("os.chdir"), \
                patch("pathlib.Path.is_dir", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "Reiniciar sessão"):
                exec(compile(codigo, "setup-colab", "exec"), {})
        self.assertEqual(executar.call_args_list[0], call(
            ["git", "-C", "/content/Downloader-Universal", "pull", "--ff-only"], check=True))


if __name__ == "__main__":
    unittest.main()
