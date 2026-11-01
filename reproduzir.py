"""Execute: python reproduzir.py --verificar (ou --corte 0, 1, 2)."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Evita que operações minúsculas de álgebra linear abram muitas threads.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

from modelo import ORIGENS, DESTINOS, criar_prior, atualizar_com_apuracao, prever
from graficos import salvar_distribuicoes, salvar_trajetoria

ROOT = Path(__file__).resolve().parent


def resumo(cut, theta, result=None):
    return {
        "corte": cut, "media_lula_pct": float(theta.mean()),
        "p025": float(np.quantile(theta, 0.025)), "p975": float(np.quantile(theta, 0.975)),
        "n_cenarios": len(theta), "acima_50": int((theta > 50).sum()),
        "fracao_acima_50_pct": float(100 * np.mean(theta > 50)),
        "lambda": None if result is None else result["lambda"],
        "secoes": 0 if result is None else result["n_sections"],
        "municipios": 0 if result is None else result["n_municipalities"],
    }


def conferir_referencia(rows, matrices):
    """A referência é aberta só depois de estimar; nunca entra no ajuste."""
    reference = json.loads((ROOT / "referencia.json").read_text(encoding="utf-8"))
    for row in rows:
        target = reference["forecasts"][int(row["corte"])]
        np.testing.assert_allclose(row["media_lula_pct"], target["mean_pct"], atol=1e-6, rtol=0)
        np.testing.assert_allclose([row["p025"], row["p975"]], target["interval95_pct"], atol=1e-6, rtol=0)
        assert row["acima_50"] == target["n_lula_gt50"]
        assert row["n_cenarios"] == target["n_draws"]
        if row["corte"] != "0":
            assert row["lambda"] == target["lambda"]
            np.testing.assert_allclose(matrices[row["corte"]], reference["point_coefficients"][row["corte"]], atol=1e-7, rtol=0)
    print("Referência conferida: previsões, contagens, intervalos, lambda e coeficientes.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corte", choices=["0", "1", "2", "todos"], default="todos")
    parser.add_argument("--saida", type=Path, default=ROOT / "resultados")
    parser.add_argument("--verificar", action="store_true", help="Compara a execução com os números publicados, depois de estimar.")
    args = parser.parse_args()
    output = args.saida.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = ROOT / "dados"
    # Zero urnas: só estes três insumos anteriores ao segundo turno são lidos.
    inputs = ["pesquisa_e_cortes.json", "historico_nacional.csv", "baseline_2026_1t.csv"]
    protocol = json.loads((data / inputs[0]).read_text(encoding="utf-8"))
    history = pd.read_csv(data / inputs[1])
    baseline = pd.read_csv(data / inputs[2]).iloc[0]
    if set(history.ano) != {2014, 2018, 2022} or len(history) != 3:
        raise ValueError("O histórico precisa conter somente 2014, 2018 e 2022.")
    if baseline.ano != 2026 or protocol["poll"]["publication"] >= "2026-10-25":
        raise ValueError("Baseline ou pesquisa fora da janela anterior ao segundo turno.")
    print("Gerando 10.000 cenários de prior, sem abrir dados da apuração…", flush=True)
    prior, national_origins = criar_prior(protocol, history, baseline)
    theta0 = prever(prior, national_origins, np.zeros(2))
    scenarios, rows, coefficients, matrices, results = {}, [], [], {}, {}
    cuts = ["0", "1", "2"] if args.corte == "todos" else [args.corte]
    for cut in cuts:
        if cut == "0":
            draws, point, theta = prior, prior.mean(axis=0), theta0
            result = None
        else:
            name = f"apuracao_{cut}pct.csv"
            inputs.append(name)
            frame = pd.read_csv(data / name, dtype={"secao": str, "municipio": str}, parse_dates=["apurada_em"])
            meta = protocol["cuts"][cut]
            if frame.apurada_em.isna().any() or frame.apurada_em.max() > pd.Timestamp(meta["timestamp"]):
                raise ValueError("O arquivo contém horário ausente ou posterior ao corte.")
            if len(frame) != meta["sections"] or frame.secao.duplicated().any() or frame.municipio.nunique() != meta["municipalities"]:
                raise ValueError("Contagem de seções ou municípios inconsistente.")
            counts = frame[["L1", "F1", "O1", "BN1", "A1", "L2", "F2"]].to_numpy(float)
            if not np.isfinite(counts).all() or (counts < 0).any() or (counts[:, :5].sum(axis=1) <= 0).any():
                raise ValueError("Contagens inválidas.")
            print(f"Ajustando corte de ≈{cut}%: {len(frame):,} seções…", flush=True)
            result = atualizar_com_apuracao(frame, prior, national_origins)
            results[cut] = result
            draws, point, theta = result["draws"], result["point"], result["theta"]
            pd.DataFrame(result["cv"]).to_csv(output / f"validacao_cruzada_{cut}pct.csv", index=False)
        np.testing.assert_allclose(draws.sum(axis=2), 1, rtol=0, atol=1e-10)
        assert (draws > 0).all()
        scenarios[cut], matrices[cut] = theta, point
        rows.append(resumo(cut, theta, result))
        pd.DataFrame({"cenario": np.arange(1, len(theta)+1), "lula_pct": theta}).to_csv(output / f"cenarios_{cut}pct.csv", index=False)
        np.savez_compressed(output / f"coeficientes_{cut}pct.npz", beta=draws, beta_pontual=point)
        for g, origin in enumerate(ORIGENS):
            for d, destination in enumerate(DESTINOS):
                coefficients.append({"corte": cut, "origem": origin, "destino": destination,
                                     "prior_media": float(prior[:, g, d].mean()),
                                     "beta_pontual": float(point[g, d]), "media_cenarios": float(draws[:, g, d].mean()),
                                     "p025": float(np.quantile(draws[:, g, d], 0.025)), "p975": float(np.quantile(draws[:, g, d], 0.975))})
    table = pd.DataFrame(rows)
    table.to_csv(output / "previsoes.csv", index=False)
    pd.DataFrame(coefficients).to_csv(output / "coeficientes.csv", index=False)
    salvar_distribuicoes(scenarios, output)
    if "2" in results:
        name = "ordem_hipotetica_origens.csv"
        inputs.append(name)
        order = pd.read_csv(data / name)
        salvar_trajetoria(order, results["2"], protocol["domestic_sections"], output)
    print("\n" + table.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    if args.verificar:
        conferir_referencia(rows, matrices)
    execution = {
        "corte": args.corte, "resultados": rows,
        "insumos_lidos_sha256": {name: hashlib.sha256((data/name).read_bytes()).hexdigest() for name in inputs},
        "interpretacao": "Frequências condicionais aos priors e ao bootstrap. Não são amostras de um posterior MCMC nem probabilidades empiricamente calibradas.",
    }
    (output / "execucao.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nArquivos gerados em: {output}")


if __name__ == "__main__":
    main()
