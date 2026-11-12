import os
import tempfile
import unittest
from unittest import mock

from nvrbox import rede

MAC_LATERAL = "02:0a:bc:de:00:01"
MAC_QUINTAL = "02:0a:bc:de:00:02"


class TabelaArpTest(unittest.TestCase):
    def test_le_so_entradas_completas(self):
        conteudo = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.0.3      0x1         0x2         02:0A:BC:DE:00:02     *        end0\n"
            "192.168.0.7      0x1         0x0         10:7c:61:a5:a6:93     *        end0\n"
            "192.168.0.9      0x1         0x2         00:00:00:00:00:00     *        end0\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as arquivo:
            arquivo.write(conteudo)
        try:
            with mock.patch.object(rede, "ARQUIVO_ARP", arquivo.name):
                self.assertEqual(rede.ler_tabela_arp(), {"192.168.0.3": MAC_QUINTAL})
        finally:
            os.remove(arquivo.name)

    def test_sem_acesso_a_tabela_retorna_none(self):
        with (
            mock.patch.object(rede, "ARQUIVO_ARP", "/caminho/inexistente"),
            mock.patch.object(rede.subprocess, "run", side_effect=OSError),
        ):
            self.assertIsNone(rede.ler_tabela_arp())

    def test_normalizar_mac(self):
        self.assertEqual(rede.normalizar_mac("02-0A-BC-DE-00-02"), MAC_QUINTAL)
        self.assertIsNone(rede.normalizar_mac(""))
        self.assertIsNone(rede.normalizar_mac("nao e mac"))


class LocalizarCameraTest(unittest.TestCase):
    def localizar(self, mac, ip, tabela, tabela_apos_varredura=None):
        varreduras = []

        def varrer(ip_referencia, porta):
            varreduras.append(ip_referencia)
            return tabela_apos_varredura if tabela_apos_varredura is not None else tabela

        resultado = rede.localizar_camera(
            mac, ip, 554,
            ler_arp=lambda: tabela, tocar=lambda ip, porta: False, varrer=varrer,
            mac_onvif=lambda ip: None,
        )
        return resultado, varreduras

    def test_ip_confirmado_nao_varre_a_rede(self):
        resultado, varreduras = self.localizar(MAC_LATERAL, "192.168.0.2", {"192.168.0.2": MAC_LATERAL})
        self.assertEqual(resultado, ("192.168.0.2", "confirmada"))
        self.assertEqual(varreduras, [])

    def test_cameras_trocadas_sao_encontradas_sem_varrer(self):
        tabela = {"192.168.0.2": MAC_QUINTAL, "192.168.0.3": MAC_LATERAL}
        self.assertEqual(self.localizar(MAC_LATERAL, "192.168.0.2", tabela)[0], ("192.168.0.3", "mudou"))
        self.assertEqual(self.localizar(MAC_QUINTAL, "192.168.0.3", tabela)[0], ("192.168.0.2", "mudou"))

    def test_camera_fora_da_tabela_e_achada_pela_varredura(self):
        resultado, varreduras = self.localizar(
            MAC_LATERAL, "192.168.0.2", {}, tabela_apos_varredura={"192.168.0.23": MAC_LATERAL}
        )
        self.assertEqual(resultado, ("192.168.0.23", "mudou"))
        self.assertEqual(varreduras, ["192.168.0.2"])

    def test_camera_desligada_nao_e_encontrada(self):
        resultado, _ = self.localizar(MAC_LATERAL, "192.168.0.2", {"192.168.0.1": "28:ee:52:d9:9a:d8"})
        self.assertEqual(resultado, (None, "nao_encontrada"))

    def test_sem_mac_ou_sem_tabela_nao_bloqueia(self):
        self.assertEqual(self.localizar("", "192.168.0.2", {})[0], ("192.168.0.2", "sem_verificacao"))
        self.assertEqual(self.localizar(MAC_LATERAL, "192.168.0.2", None)[0], ("192.168.0.2", "sem_verificacao"))


class LocalizarSemArpTest(unittest.TestCase):

    def localizar(self, mac, ip, onvif, tabela_varredura):
        varreduras = []

        def varrer(ip_referencia, porta):
            varreduras.append(ip_referencia)
            return tabela_varredura

        resultado = rede.localizar_camera(
            mac, ip, 554, ler_arp=lambda: None, varrer=varrer, mac_onvif=lambda alvo: onvif.get(alvo),
        )
        return resultado, varreduras

    def test_ip_confirmado_pelo_onvif_nao_varre(self):
        resultado, varreduras = self.localizar(MAC_LATERAL, "192.168.0.3", {"192.168.0.3": MAC_LATERAL}, {})
        self.assertEqual(resultado, ("192.168.0.3", "confirmada"))
        self.assertEqual(varreduras, [])

    def test_camera_que_mudou_de_ip_e_achada_pela_varredura(self):
        varredura = {"192.168.0.4": MAC_QUINTAL, "192.168.0.6": MAC_LATERAL}
        resultado, varreduras = self.localizar(MAC_LATERAL, "192.168.0.3", {}, varredura)
        self.assertEqual(resultado, ("192.168.0.6", "mudou"))
        self.assertEqual(varreduras, ["192.168.0.3"])

    def test_ip_ocupado_por_outra_camera_e_corrigido(self):
        onvif = {"192.168.0.3": MAC_QUINTAL}
        varredura = {"192.168.0.3": MAC_QUINTAL, "192.168.0.8": MAC_LATERAL}
        self.assertEqual(self.localizar(MAC_LATERAL, "192.168.0.3", onvif, varredura)[0], ("192.168.0.8", "mudou"))

    def test_camera_desligada_com_outras_respondendo_nao_e_encontrada(self):
        resultado, _ = self.localizar(MAC_LATERAL, "192.168.0.3", {}, {"192.168.0.4": MAC_QUINTAL})
        self.assertEqual(resultado, (None, "nao_encontrada"))

    def test_sem_nenhuma_resposta_onvif_nao_bloqueia_a_gravacao(self):
        self.assertEqual(self.localizar(MAC_LATERAL, "192.168.0.3", {}, {})[0], ("192.168.0.3", "sem_verificacao"))


class MacPeloOnvifTest(unittest.TestCase):
    def resposta(self, texto):
        corpo = mock.MagicMock()
        corpo.read.return_value = texto.encode()
        corpo.__enter__.return_value = corpo
        return corpo

    def test_extrai_mac_da_resposta(self):
        xml = "<tds:HwAddress>02-0a-bc-de-00-02</tds:HwAddress>"
        with mock.patch("urllib.request.urlopen", return_value=self.resposta(xml)):
            self.assertEqual(rede.mac_pelo_onvif("192.168.0.6"), "02:0a:bc:de:00:02")

    def test_sem_resposta_retorna_none(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError):
            self.assertIsNone(rede.mac_pelo_onvif("192.168.0.6"))


if __name__ == "__main__":
    unittest.main()
