"""Figuras geradas dos novos sorteios e ajustes, sem curvas realizadas."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

PURPLE = "#770EAE"
BLUE = "#0442AE"


def salvar_distribuicoes(scenarios, output):
    fig, axes = plt.subplots(1, len(scenarios), figsize=(5 * len(scenarios), 4), squeeze=False)
    for ax, (cut, theta) in zip(axes[0], scenarios.items()):
        low, high = (43, 56) if cut == "0" else (49.9, 52.3)
        edges = np.linspace(low, high, 70)
        # Zoom no eixo, sem renormalizar a massa das caudas que ficam de fora.
        weights = np.full(len(theta), 1 / (len(theta) * (edges[1] - edges[0])))
        ax.hist(theta, bins=edges, weights=weights, histtype="stepfilled", color=PURPLE, alpha=0.18)
        ax.hist(theta, bins=edges, weights=weights, histtype="step", color=PURPLE, linewidth=1.7)
        ax.axvline(50, color="#788494", linestyle="--", linewidth=1.2)
        ax.set_title("Zero urnas\nModelo linear com priors" if cut == "0"
                     else f"Após ≈{cut}% nacional\nWLS sem prior + bootstrap municipal", fontsize=10.5)
        above = f"{int((theta > 50).sum()):,}".replace(",", ".")
        n = f"{len(theta):,}".replace(",", ".")
        ax.text(.035, .96, f"{above}/{n} acima de 50%", transform=ax.transAxes,
                va="top", fontsize=9, color=PURPLE)
        ax.set_xlabel("Lula nos votos válidos (%)")
        ax.set_ylabel("Densidade")
        ax.set_xlim(low, high)
        ax.margins(y=0.18)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.15)
    fig.tight_layout()
    for extension in ("png", "svg"):
        fig.savefig(output / f"distribuicoes.{extension}", dpi=220, facecolor="white")
    plt.close(fig)


def salvar_trajetoria(order, result, n_total, output, cut):
    origins = order[["L1", "F1", "O1", "BN1", "A1"]].to_numpy(dtype=float)
    totals = np.einsum("ko,bod->bkd", origins, result["draws"][:, :, :2]) + result["counted_lf"]
    lula = 100 * totals[:, :, 0] / totals.sum(axis=2)
    x = 100 * (result["n_sections"] + order.secoes_pendentes_acumuladas.to_numpy()) / n_total
    mean = lula.mean(axis=0)
    lower, upper = np.quantile(lula, [0.025, 0.975], axis=0)
    frame = pd.DataFrame({"secoes_domesticas_pct": x, "lula_media_pct": mean,
                          "flavio_media_pct": 100 - mean, "lula_p025": lower, "lula_p975": upper})
    frame.to_csv(output / f"trajetoria_{cut}pct.csv", index=False)
    np.testing.assert_allclose(lula[:, -1], result["theta"], rtol=0, atol=1e-10)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x, mean, color=PURPLE, linewidth=2, label=f"Lula · {mean[-1]:.2f}%")
    ax.plot(x, 100 - mean, color=BLUE, linewidth=2, label=f"Flávio · {100 - mean[-1]:.2f}%")
    ax.axhline(50, color="#788494", linestyle="--", linewidth=1)
    ax.set(xlabel="Seções apuradas (%) · Brasil sem exterior",
           ylabel="Votos válidos acumulados (%)", xlim=(0, 100), ylim=(47, 53))
    ax.set_yticks(np.arange(47, 54))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.15)
    ax.legend(frameon=False)
    fig.tight_layout()
    for extension in ("png", "svg"):
        fig.savefig(output / f"trajetoria_{cut}pct.{extension}", dpi=220, facecolor="white")
    plt.close(fig)
