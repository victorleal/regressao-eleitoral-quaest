"""Testes do corte de informação, sem dependências extras de teste."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class InformationCutTests(unittest.TestCase):
    def test_hashes_dos_insumos(self):
        manifest = json.loads((ROOT / "dados/fontes.json").read_text(encoding="utf-8"))
        for name, expected in manifest["sha256"].items():
            actual = hashlib.sha256((ROOT / "dados" / name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)

    def run_isolated(self, cut, future_timestamp=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dados").mkdir()
            for name in ["reproduzir.py", "modelo.py", "graficos.py", "referencia.json"]:
                shutil.copy2(ROOT / name, root / name)
            names = ["primeiro_turno_e_cortes.json"]
            if cut == "0":
                names += ["quaest.json", "historico_nacional.csv", "baseline_2026_1t.csv"]
            if cut in ["1", "2"]:
                names += [f"apuracao_{cut}pct.csv", f"ordem_hipotetica_{cut}pct.csv"]
            for name in names:
                shutil.copy2(ROOT / "dados" / name, root / "dados" / name)
            if future_timestamp:
                import pandas as pd
                path = root / "dados/apuracao_1pct.csv"
                frame = pd.read_csv(path)
                frame.loc[0, "apurada_em"] = "2026-10-25 23:59:59"
                frame.to_csv(path, index=False)
            return subprocess.run(
                [sys.executable, str(root / "reproduzir.py"), "--corte", cut, "--verificar"],
                cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=90,
            )

    def test_zero_sem_arquivos_de_apuracao(self):
        result = self.run_isolated("0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("34.630000", result.stdout)

    def test_um_porcento_sem_quaest_historico_ou_apuracao_futura(self):
        result = self.run_isolated("1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("51.674400", result.stdout)

    def test_horario_posterior_ao_corte_e_rejeitado(self):
        result = self.run_isolated("1", future_timestamp=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("posterior ao corte", result.stderr)

    def test_dois_porcento_sem_quaest_ou_historico_de_participacao(self):
        result = self.run_isolated("2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("51.645116", result.stdout)


if __name__ == "__main__":
    unittest.main()
