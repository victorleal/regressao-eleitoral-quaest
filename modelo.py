"""As contas do exercício: prior, regressão composicional e previsão.

Origens (linhas de beta): Lula, Flávio, Outros, branco/nulo, ausência no 1º turno.
Destinos (colunas de beta): Lula, Flávio, branco/nulo, ausência no 2º turno.
Não há intercepto extra nem efeitos fixos. Só L/F são respostas observadas.
"""
import numpy as np

ORIGENS = ["Lula", "Flávio", "Outros", "Branco/nulo", "Ausência"]
DESTINOS = ["Lula", "Flávio", "Branco/nulo", "Ausência"]
GRADE_LAMBDA = np.array([0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0])
SEED_FOLDS = 20261029011
SEED_PRIOR = 20261029012
SEED_BOOTSTRAP = 20261029013
N_CENARIOS = 600


def sortear_participacao(historico, primeiro_turno):
    """100 mil sorteios de comparecimento/BN a partir de 2014, 2018 e 2022.

    Para cada mudança histórica, uso a preditiva Student-t do modelo normal
    com prior de referência p(mu, sigma²) proporcional a 1/sigma².
    Com três eleições, são dois graus de liberdade: incerteza alta.
    """
    def logit(p):
        return np.log(p) - np.log1p(-p)

    def predictive_parameters(values):
        return values.mean(), values.std(ddof=1) * np.sqrt(1 + 1 / len(values))

    h = historico
    change_attendance = 100 * (h.comparecimento_2t - h.comparecimento_1t) / h.aptos_1t
    bn1 = (h.brancos_1t + h.nulos_1t) / h.comparecimento_1t
    bn2 = (h.brancos_2t + h.nulos_2t) / h.comparecimento_2t
    change_bn = logit(bn2) - logit(bn1)
    seeds = np.random.SeedSequence(20261028).spawn(2)
    rng_attendance, rng_bn = [np.random.default_rng(s) for s in seeds]
    total = float(primeiro_turno.aptos_1t)
    attendance1 = float(primeiro_turno.comparecimento_1t)
    bn_rate1 = float((primeiro_turno.brancos_1t + primeiro_turno.nulos_1t) / attendance1)

    # Rejeito comparecimento impossível, em vez de truncá-lo nos limites.
    location, scale = predictive_parameters(change_attendance)
    chunks = []
    remaining = 100_000
    while remaining:
        change = location + scale * rng_attendance.standard_t(2, size=remaining)
        attendance = attendance1 + total * change / 100
        keep = np.isfinite(attendance) & (attendance >= 0) & (attendance <= total)
        chunks.append(change[keep])
        remaining -= int(keep.sum())
    attendance2 = attendance1 + total * np.concatenate(chunks) / 100
    location, scale = predictive_parameters(change_bn)
    change = location + scale * rng_bn.standard_t(2, size=100_000)
    t = logit(bn_rate1) + change
    exponential = np.exp(-np.abs(t))
    bn_rate2 = np.where(t >= 0, 1 / (1 + exponential), exponential / (1 + exponential))
    bn2 = attendance2 * bn_rate2

    # A mesma subamostra usada na publicação; a semente faz parte da reprodução.
    chosen = np.random.default_rng(2026102802).choice(100_000, size=10_000, replace=False)
    return np.column_stack([attendance2 - bn2, bn2, total - attendance2])[chosen]


def calibrar_participacao(probabilities, origins, targets):
    """IPF: preserva origens e ajusta somente totais de válidos, BN e ausentes.

    A proporção Lula/Flávio dentro de cada origem permanece constante.
    Nenhum total nacional de Lula ou Flávio é passado como meta.
    """
    valid = probabilities[:, :, :2].sum(axis=2)
    share_lula = probabilities[:, :, 0] / valid
    macro = np.stack([valid, probabilities[:, :, 2], probabilities[:, :, 3]], axis=2)
    macro *= origins[None, :, None]
    active = np.ones(len(probabilities), dtype=bool)
    tolerance = origins.sum() * 1e-10
    for _ in range(4000):
        indices = np.flatnonzero(active)
        work = macro[indices]
        desired = targets[indices]
        work *= (desired / work.sum(axis=1))[:, None, :]
        work *= (origins[None, :] / work.sum(axis=2))[:, :, None]
        macro[indices] = work
        col_error = np.max(np.abs(work.sum(axis=1) - desired), axis=1)
        row_error = np.max(np.abs(work.sum(axis=2) - origins[None, :]), axis=1)
        active[indices[np.maximum(col_error, row_error) <= tolerance]] = False
        if not active.any():
            break
    if active.any():
        raise RuntimeError("A calibração de participação não convergiu.")
    counts = np.empty_like(probabilities)
    counts[:, :, 0] = macro[:, :, 0] * share_lula
    counts[:, :, 1] = macro[:, :, 0] * (1 - share_lula)
    counts[:, :, 2:] = macro[:, :, 1:]
    return counts / origins[None, :, None]


def criar_prior(protocol, historico, primeiro_turno):
    """Transforma as quatro linhas da Quaest em 10 mil matrizes beta (5 x 4).

    A agregação de Outros só ocorre depois da calibração, para preservar
    exatamente a contabilidade e os sorteios da versão publicada.
    """
    atoms = protocol["origin_atoms"]
    names = list(atoms)
    origins = np.array(list(atoms.values()), dtype=float)
    targets = sortear_participacao(historico, primeiro_turno)
    rng = np.random.default_rng(2026104803)
    probabilities = np.empty((10_000, len(origins), 4))
    for row in protocol["poll"]["rows"]:
        p_lula, p_flavio = row["lula"] / 100, row["flavio"] / 100
        residual = max(0.0, 1 - p_lula - p_flavio)
        split = rng.beta(1.0, 1.0, 10_000)
        p = np.column_stack([
            np.full(10_000, p_lula), np.full(10_000, p_flavio),
            residual * split, residual * (1 - split),
        ])
        # Gamma normalizada é uma forma de sortear a Dirichlet.
        gamma = np.maximum(rng.gamma(0.5 + 100 * p), np.finfo(float).tiny)
        draw = gamma / gamma.sum(axis=1, keepdims=True)
        for member in row["members"]:
            probabilities[:, names.index(member), :] = draw

    for origin, return_destination in [("A", 3), ("BN", 2)]:
        q = rng.uniform(0, 1, 10_000)
        i = names.index(origin)
        removed = (1 - q) * probabilities[:, i, :2].sum(axis=1)
        probabilities[:, i, :2] *= q[:, None]
        probabilities[:, i, return_destination] += removed
    beta = calibrar_participacao(probabilities, origins, targets)
    groups = [["13"], ["22"], [n for n in names if n not in ("13", "22", "BN", "A")], ["BN"], ["A"]]
    mapping = np.array([[float(n in group) for n in names] for group in groups])
    total_origins = mapping @ origins
    weights = mapping * origins[None, :] / total_origins[:, None]
    beta = np.einsum("go,bod->bgd", weights, beta, optimize=True)
    return beta, total_origins


def ajustar_regressao(G, H, prior, lam, start=None):
    """Minimiza mínimos quadrados ponderados + lambda * KL(prior || beta).

    G = X'WX; H = X'WY (colunas BN/A são zeros de armazenamento).
    Cada linha de beta é positiva e soma 1. Só L/F entram no erro quadrático.
    Uso Newton com busca de passo; a dimensão do sistema é apenas 15.
    """
    mask = np.array([1.0, 1.0, 0.0, 0.0])
    G = 0.5 * (G + G.T)
    beta = prior.copy() if start is None else start.copy()
    beta /= beta.sum(axis=1, keepdims=True)
    # A quarta coluna é 1 menos a soma das três primeiras, em cada linha.
    Z = np.zeros((20, 15))
    for g in range(5):
        Z[4*g:4*g+3, 3*g:3*g+3] = np.eye(3)
        Z[4*g+3, 3*g:3*g+3] = -1
    quadratic = np.kron(G, np.diag(mask))

    def objective(b):
        return float(0.5 * np.sum(b * (G @ b) * mask) - np.sum(H * b)
                     + lam * np.sum(prior * (np.log(prior) - np.log(b))))

    for _ in range(351):
        gradient = (G @ beta) * mask - H - lam * prior / beta
        projected = gradient - gradient.mean(axis=1, keepdims=True)
        scale = 1 + max(float(np.abs((G @ beta) * mask).max()),
                        float(np.abs(H).max()), float(np.abs(lam * prior / beta).max()))
        if np.abs(projected).max() / scale <= 1e-9:
            return beta
        hessian = quadratic + np.diag((lam * prior / beta**2).ravel())
        reduced_gradient = Z.T @ gradient.ravel()
        reduced_direction = np.linalg.solve(Z.T @ hessian @ Z, -reduced_gradient)
        direction = (Z @ reduced_direction).reshape(5, 4)
        slope = float(reduced_gradient @ reduced_direction)
        negative = direction < 0
        step = min(1.0, 0.99 * float(np.min(-beta[negative] / direction[negative]))) if negative.any() else 1.0
        current = objective(beta)
        for _ in range(80):
            trial = beta + step * direction
            if (trial > 0).all():
                trial /= trial.sum(axis=1, keepdims=True)
                if objective(trial) <= current + 1e-4 * step * slope + 1e-13 * (1 + abs(current)):
                    beta = trial
                    break
            step *= 0.5
        else:
            raise RuntimeError("Não encontrei um passo que reduza a função objetivo.")
    raise RuntimeError("A regressão não convergiu.")


def prever(beta, pending_origins, counted_lf):
    """Votos já contados ficam fixos; beta só estima os votos pendentes."""
    future = np.einsum("o,bod->bd", pending_origins, beta)
    totals = future[:, :2] + counted_lf
    return 100 * totals[:, 0] / totals.sum(axis=1)


def atualizar_com_apuracao(frame, prior, total_origins, progress=print):
    """CV por município, ajuste pontual e 600 pares prior/bootstrap municipal."""
    counts = frame[["L1", "F1", "O1", "BN1", "A1"]].to_numpy(dtype=float)
    N = counts.sum(axis=1)
    X = counts / N[:, None]
    lf = frame[["L2", "F2"]].to_numpy(dtype=float)
    Y = np.zeros((len(X), 4))
    Y[:, :2] = lf / N[:, None]  # BN/A não viram respostas artificiais.
    clusters, codes = np.unique(frame.municipio.to_numpy(), return_inverse=True)
    n_clusters = len(clusters)
    folds = np.empty(n_clusters, dtype=int)
    folds[np.random.default_rng(SEED_FOLDS).permutation(n_clusters)] = np.arange(n_clusters) % 5
    Gg = np.zeros((n_clusters, 5, 5))
    Hg = np.zeros((n_clusters, 5, 4))
    Ng = np.zeros(n_clusters)
    Mg = np.zeros(n_clusters)
    for g in range(n_clusters):
        take = codes == g
        x, n = X[take], N[take]
        Gg[g] = x.T @ (n[:, None] * x)
        Hg[g] = x.T @ (n[:, None] * Y[take])
        Ng[g], Mg[g] = n.sum(), take.sum()

    def normalize(g, h, n, m):
        return g / (n / m), h / (n / m)

    mu = prior.mean(axis=0)
    cv = []
    for lam in GRADE_LAMBDA:
        error = 0.0
        for fold in range(5):
            train, held = folds != fold, folds[codes] == fold
            g, h = normalize(Gg[train].sum(axis=0), Hg[train].sum(axis=0), Ng[train].sum(), Mg[train].sum())
            beta = ajustar_regressao(g, h, mu, float(lam))
            residual = Y[held, :2] - (X[held] @ beta)[:, :2]
            error += float(np.sum(N[held] * np.sum(residual**2, axis=1)))
        cv.append({"lambda": float(lam), "erro_cv": error / N.sum()})
    lam = min(cv, key=lambda row: row["erro_cv"])["lambda"]
    G, H = normalize(Gg.sum(axis=0), Hg.sum(axis=0), Ng.sum(), Mg.sum())
    point = ajustar_regressao(G, H, mu, lam)
    chosen = np.random.default_rng(SEED_PRIOR).choice(len(prior), size=N_CENARIOS, replace=False)
    multipliers = np.random.default_rng(SEED_BOOTSTRAP).multinomial(n_clusters, np.full(n_clusters, 1/n_clusters), size=N_CENARIOS)
    draws = np.empty((N_CENARIOS, 5, 4))
    for j, mult in enumerate(multipliers):
        g, h = normalize(np.einsum("g,gij->ij", mult, Gg), np.einsum("g,gij->ij", mult, Hg), float(mult @ Ng), float(mult @ Mg))
        draws[j] = ajustar_regressao(g, h, prior[chosen[j]], lam, start=point)
        if (j + 1) % 200 == 0:
            progress(f"  {j + 1}/{N_CENARIOS} reajustes concluídos")
    pending = total_origins - counts.sum(axis=0)
    counted = lf.sum(axis=0)
    return {
        "draws": draws, "point": point, "lambda": lam, "cv": cv,
        "theta": prever(draws, pending, counted),
        "point_theta": float(prever(point[None], pending, counted)[0]),
        "n_sections": len(frame), "n_municipalities": n_clusters,
        "counted_lf": counted,
    }
