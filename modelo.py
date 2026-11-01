"""As contas do exercício: prior, regressão composicional e previsão.

Origens (linhas de beta): Lula, Flávio, Outros, branco/nulo, ausência no 1º turno.
Zero urnas: quatro destinos sorteados, com Quaest e hipóteses de participação.
Com urnas: só Lula/Flávio são estimados, por WLS restrita sem pesquisa ou prior.
Não há intercepto extra nem efeitos fixos.
"""
import numpy as np

ORIGENS = ["Lula", "Flávio", "Outros", "Branco/nulo", "Ausência"]
DESTINOS = ["Lula", "Flávio", "Branco/nulo", "Ausência"]
SEED_BOOTSTRAP = 20261029013
N_SORTEIOS_PARTICIPACAO = 100_000
N_SIMULACOES = 10_000
N_BOOTSTRAPS = 600


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
    remaining = N_SORTEIOS_PARTICIPACAO
    while remaining:
        change = location + scale * rng_attendance.standard_t(2, size=remaining)
        attendance = attendance1 + total * change / 100
        keep = np.isfinite(attendance) & (attendance >= 0) & (attendance <= total)
        chunks.append(change[keep])
        remaining -= int(keep.sum())
    attendance2 = attendance1 + total * np.concatenate(chunks) / 100
    location, scale = predictive_parameters(change_bn)
    change = location + scale * rng_bn.standard_t(2, size=N_SORTEIOS_PARTICIPACAO)
    t = logit(bn_rate1) + change
    exponential = np.exp(-np.abs(t))
    bn_rate2 = np.where(t >= 0, 1 / (1 + exponential), exponential / (1 + exponential))
    bn2 = attendance2 * bn_rate2

    # A mesma subamostra usada na publicação; a semente faz parte da reprodução.
    chosen = np.random.default_rng(2026102802).choice(
        N_SORTEIOS_PARTICIPACAO, size=N_SIMULACOES, replace=False)
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
    """Sorteia coeficientes a partir da Quaest, sem estimar uma regressão.

    A agregação de Outros só ocorre depois da calibração, para preservar
    exatamente a contabilidade e os sorteios da versão publicada.
    """
    atoms = protocol["origin_atoms"]
    names = list(atoms)
    origins = np.array(list(atoms.values()), dtype=float)
    targets = sortear_participacao(historico, primeiro_turno)
    rng = np.random.default_rng(2026104803)
    probabilities = np.empty((N_SIMULACOES, len(origins), 4))
    for row in protocol["poll"]["rows"]:
        p_lula, p_flavio = row["lula"] / 100, row["flavio"] / 100
        residual = max(0.0, 1 - p_lula - p_flavio)
        split = rng.beta(1.0, 1.0, N_SIMULACOES)
        p = np.column_stack([
            np.full(N_SIMULACOES, p_lula), np.full(N_SIMULACOES, p_flavio),
            residual * split, residual * (1 - split),
        ])
        # Gamma normalizada é uma forma de sortear a Dirichlet.
        gamma = np.maximum(rng.gamma(0.5 + 100 * p), np.finfo(float).tiny)
        draw = gamma / gamma.sum(axis=1, keepdims=True)
        for member in row["members"]:
            probabilities[:, names.index(member), :] = draw

    for origin, return_destination in [("A", 3), ("BN", 2)]:
        q = rng.uniform(0, 1, N_SIMULACOES)
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


def ajustar_sem_prior(G, H, start=None):
    """WLS convexa: beta_L >= 0, beta_F >= 0, beta_L + beta_F <= 1.

    Só os dois candidatos são estimados. O residual BN + ausência não é
    separado: não há respostas que identifiquem essa divisão.
    """
    from scipy.optimize import minimize, LinearConstraint, Bounds

    A = np.zeros((5, 10))
    for g in range(5):
        A[g, 2*g:2*g+2] = 1
    initial = np.full((5, 2), 0.25) if start is None else start
    scale = max(1.0, float(np.max(abs(G))))

    def objective(z):
        beta = z.reshape(5, 2)
        return float(0.5 * np.sum(beta * (G @ beta)) - np.sum(H * beta)) / scale

    def gradient(z):
        return (G @ z.reshape(5, 2) - H).ravel() / scale

    fit = minimize(objective, initial.ravel(), jac=gradient, method="SLSQP",
                   bounds=Bounds(np.zeros(10), np.ones(10)),
                   constraints=[LinearConstraint(A, -np.inf, 1)],
                   options={"ftol": 1e-13, "maxiter": 400})
    if not fit.success:
        raise RuntimeError(fit.message)
    beta = fit.x.reshape(5, 2)
    # Identificadas as restrições ativas, resolvo o sistema linear de KKT.
    # Isso remove o erro numérico associado ao ponto inicial do otimizador.
    active, values = [], []
    for index in np.flatnonzero(beta.ravel() < 1e-7):
        row = np.zeros(10)
        row[index] = 1
        active.append(row)
        values.append(0.0)
    for g in np.flatnonzero(beta.sum(axis=1) > 1 - 1e-7):
        active.append(A[g])
        values.append(1.0)
    if active:
        C = np.asarray(active)
        Q = np.kron(G, np.eye(2))
        system = np.block([[Q, C.T], [C, np.zeros((len(C), len(C)))]])
        beta = np.linalg.solve(system, np.r_[H.ravel(), values])[:10].reshape(5, 2)
    else:
        beta = np.linalg.solve(G, H)
    if beta.min() < -1e-9 or beta.sum(axis=1).max() > 1 + 1e-9:
        raise RuntimeError("Solução fora das restrições composicionais.")
    grad = G @ beta - H
    multipliers = np.zeros(5)
    for g in range(5):
        if beta[g].sum() > 1 - 1e-7:
            multipliers[g] = -np.mean(grad[g, beta[g] > 1e-7])
    reduced = grad + multipliers[:, None]
    kkt = max(float(np.max(abs(reduced[beta > 1e-7]))),
              float(np.max(np.maximum(-reduced[beta <= 1e-7], 0))) if (beta <= 1e-7).any() else 0,
              float(np.max(np.maximum(-multipliers, 0)))) / scale
    if kkt >= 3e-6:
        raise RuntimeError(f"Condições de ótimo não satisfeitas: {kkt}")
    return beta, kkt


def prever(beta, pending_origins, counted_lf):
    """Aplica os coeficientes às pendências e soma os votos contados fixos.

    beta pode ter sido sorteado ou estimado. Esta função só calcula a
    projeção; não estima coeficientes nem sorteia uma votação diretamente.
    """
    future = np.einsum("o,bod->bd", pending_origins, beta)
    totals = future[:, :2] + counted_lf
    return 100 * totals[:, 0] / totals.sum(axis=1)


def atualizar_com_apuracao(frame, total_origins, progress=print):
    """Estima só com as urnas do corte e faz 600 bootstraps municipais.

    Esta função não recebe prior, pesquisa, coeficientes iniciais externos
    ou parâmetro de penalização. O ponto inicial é uma constante neutra.
    """
    counts = frame[["L1", "F1", "O1", "BN1", "A1"]].to_numpy(dtype=float)
    N = counts.sum(axis=1)
    X = counts / N[:, None]
    lf = frame[["L2", "F2"]].to_numpy(dtype=float)
    Y = lf / N[:, None]
    clusters, codes = np.unique(frame.municipio.to_numpy(), return_inverse=True)
    n_clusters = len(clusters)
    Gg = np.zeros((n_clusters, 5, 5))
    Hg = np.zeros((n_clusters, 5, 2))
    Ng = np.zeros(n_clusters)
    Mg = np.zeros(n_clusters)
    for g in range(n_clusters):
        take = codes == g
        x, n = X[take], N[take]
        Gg[g] = x.T @ (n[:, None] * x)
        Hg[g] = x.T @ (n[:, None] * Y[take])
        Ng[g], Mg[g] = n.sum(), take.sum()
    scale = Ng.sum() / Mg.sum()
    point, max_kkt = ajustar_sem_prior(Gg.sum(axis=0)/scale, Hg.sum(axis=0)/scale)
    multipliers = np.random.default_rng(SEED_BOOTSTRAP).multinomial(
        n_clusters, np.full(n_clusters, 1/n_clusters), size=N_BOOTSTRAPS)
    draws = np.empty((N_BOOTSTRAPS, 5, 2))
    for j, mult in enumerate(multipliers):
        scale = float(mult @ Ng) / float(mult @ Mg)
        g = np.einsum("g,gij->ij", mult, Gg) / scale
        h = np.einsum("g,gij->ij", mult, Hg) / scale
        draws[j], kkt = ajustar_sem_prior(g, h, start=point)
        max_kkt = max(max_kkt, kkt)
        if (j + 1) % 200 == 0:
            progress(f"  {j + 1}/{N_BOOTSTRAPS} bootstraps concluídos")
    pending = total_origins - counts.sum(axis=0)
    counted = lf.sum(axis=0)
    return {"draws": draws, "point": point,
            "theta": prever(draws, pending, counted),
            "point_theta": float(prever(point[None], pending, counted)[0]),
            "n_sections": len(frame), "n_municipalities": n_clusters,
            "counted_lf": counted, "max_kkt": max_kkt}
