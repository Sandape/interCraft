"""2-PL IRT engine — probability, log-likelihood, Newton-Raphson θ estimation.

Per specs/030-irt-adaptive-diagnosis/plan.md §"2-PL Model — Math Specification".

The 2-parameter logistic (2-PL) model:

    P(u=1 | θ; a, b) = 1 / (1 + exp(-a(θ - b))) = σ(a(θ - b))

Parameters
----------
a : float
    Discrimination (slope at b). a > 0; typical range [0.3, 2.5].
b : float
    Difficulty (ability at which P = 0.5). Typical range [-3, 3].

Closed-form gradient (binary responses u_i ∈ {0, 1}):

    dℓ/dθ = Σ_i a_i (u_i - P_i(θ))

Closed-form Hessian (negative definite for a_i > 0):

    d²ℓ/dθ² = -Σ_i a_i² P_i(θ)(1 - P_i(θ))

Newton-Raphson update:

    θ_{k+1} = θ_k + Σ_i a_i (u_i - P_i(θ_k)) / Σ_i a_i² P_i(θ_k)(1 - P_i(θ_k))

Convergence: |θ_{k+1} - θ_k| < tol (default 0.01 logit) OR max_iter reached.
Standard error: SE(θ̂) = 1 / sqrt(-H(θ̂)).

Edge handling
-------------
- P clamped to [ε, 1-ε] (ε=1e-9) before log() to guard all-correct /
  all-incorrect edge cases.
- Items with a≈0 (zero discrimination) contribute nothing to gradient or
  Hessian — skipped in the sum to avoid divide-by-zero.
- Newton-Raphson θ search bounded to [-THETA_BOUND, THETA_BOUND] to keep
  estimates inside plausible logit range.

The module imports nothing from FastAPI / SQLAlchemy / structlog — it's
pure math, unit-testable without infrastructure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Probability floor for log() safety. Chosen tight enough to keep theta
# estimates numerically reasonable even with extreme parameter combos.
_PROB_EPSILON: float = 1e-9

# Hard cap on |θ|. Theoretically θ ∈ (-∞, +∞), but 6 logits ≈ 99.99% of
# the population distribution under standard normal ability prior. Clamping
# here prevents runaway Newton steps when item parameters are extreme.
THETA_BOUND: float = 6.0

# Default Newton-Raphson parameters. Convergence is empirically achieved
# in <10 iterations for n_items >= 3 with reasonable (a, b) parameters.
DEFAULT_MAX_ITER: int = 25
DEFAULT_TOL: float = 0.01

# A discrimination parameter below this threshold contributes <0.01% of
# the information of a typical a=1.0 item, so it is treated as zero.
_MIN_DISCRIMINATION: float = 1e-6


@dataclass(frozen=True)
class ThetaResult:
    """Result of Newton-Raphson MLE θ estimation.

    Attributes
    ----------
    theta : float
        Estimated user ability (logit scale).
    standard_error : float
        SE(θ̂) = 1/sqrt(-H(θ̂)) using observed information.
    n_items : int
        Number of items used in estimation (zero-discrimination items
        still count; only the empty input short-circuits).
    converged : bool
        True if |θ_{k+1} - θ_k| < tol within max_iter.
    iterations : int
        Newton-Raphson iterations executed.
    """

    theta: float
    standard_error: float
    n_items: int
    converged: bool
    iterations: int


# ── Probability & likelihood primitives ────────────────────────────────────


def probability_2pl(theta: float, a: float, b: float) -> float:
    """Return P(correct | θ; a, b) under the 2-PL model.

    P = σ(a(θ - b)) where σ is the logistic sigmoid.

    Examples
    --------
    >>> probability_2pl(0.0, 1.0, 0.0)
    0.5
    >>> round(probability_2pl(10.0, 1.0, 0.0), 4)
    0.9999
    >>> round(probability_2pl(-10.0, 1.0, 0.0), 6)
    1e-05
    """
    # Numerically stable logistic sigmoid. math.expit was added in
    # Python 3.12 but the project targets 3.11 (see pyproject.toml), so
    # we implement the stable form manually:
    #   σ(x) = 1 / (1 + exp(-x))   for x >= 0
    #   σ(x) = exp(x) / (1 + exp(x))   for x < 0
    # This avoids overflow at |x| > ~700.
    x = a * (theta - b)
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _clamp_probability(p: float) -> float:
    """Clamp P to [ε, 1-ε] to guard log(0) at extreme parameter combos."""
    if p < _PROB_EPSILON:
        return _PROB_EPSILON
    if p > 1.0 - _PROB_EPSILON:
        return 1.0 - _PROB_EPSILON
    return p


def log_likelihood(
    theta: float,
    responses: list[tuple[float, float, int]],
) -> float:
    """Log-likelihood of θ given observed (a, b, u) triples.

    Parameters
    ----------
    theta : float
        Candidate ability value.
    responses : list[tuple[float, float, int]]
        List of (a, b, u) where u ∈ {0, 1}.

    Returns
    -------
    float
        Sum_i [ u_i log P_i + (1-u_i) log(1-P_i) ].

    Notes
    -----
    P is clamped to [ε, 1-ε] before log to keep ℓ finite for all-correct
    or all-incorrect edge cases.
    """
    ll = 0.0
    for a, b, u in responses:
        p = _clamp_probability(probability_2pl(theta, a, b))
        if u:
            ll += math.log(p)
        else:
            ll += math.log(1.0 - p)
    return ll


def gradient(theta: float, responses: list[tuple[float, float, int]]) -> float:
    """First derivative dℓ/dθ at the candidate θ.

    Closed form: dℓ/dθ = Σ_i a_i (u_i - P_i(θ)).
    """
    g = 0.0
    for a, b, u in responses:
        if a < _MIN_DISCRIMINATION:
            continue  # zero-discrimination item: no information
        p = probability_2pl(theta, a, b)
        g += a * (u - p)
    return g


def hessian(theta: float, responses: list[tuple[float, float, int]]) -> float:
    """Second derivative d²ℓ/dθ² at the candidate θ.

    Closed form: d²ℓ/dθ² = -Σ_i a_i² P_i(θ)(1 - P_i(θ)).
    Returns a non-positive value for a_i > 0.
    """
    h = 0.0
    for a, b, _u in responses:
        if a < _MIN_DISCRIMINATION:
            continue
        p = probability_2pl(theta, a, b)
        h -= a * a * p * (1.0 - p)
    return h


# ── θ estimation ───────────────────────────────────────────────────────────


def estimate_theta_mle(
    responses: list[tuple[float, float, int]],
    *,
    max_iter: int = DEFAULT_MAX_ITER,
    tol: float = DEFAULT_TOL,
) -> ThetaResult:
    """Estimate θ via Newton-Raphson MLE on the 2-PL log-likelihood.

    Parameters
    ----------
    responses : list[tuple[float, float, int]]
        List of (a, b, u) triples. u is 1 for correct, 0 for incorrect.
        Empty list → returns the neutral estimate θ=0.0, n_items=0.
    max_iter : int
        Maximum Newton-Raphson iterations. Default 25.
    tol : float
        Convergence threshold on |θ_{k+1} - θ_k| in logits. Default 0.01.

    Returns
    -------
    ThetaResult
        Estimated θ, SE, n_items, converged flag, and iteration count.

    Notes
    -----
    - Initial θ = 0.0 (population mean on the logit scale).
    - θ update is bounded to [-THETA_BOUND, +THETA_BOUND] each step.
    - SE is 1/sqrt(-H(θ̂)) using observed (not expected) information.
    - Convergence failure returns the last-iteration θ with
      `converged=False`. The caller decides whether to trust the result.
    """
    n_items = len(responses)

    if n_items == 0:
        # No information → neutral estimate, SE reflects zero information.
        return ThetaResult(
            theta=0.0,
            standard_error=float("inf"),
            n_items=0,
            converged=True,
            iterations=0,
        )

    theta = 0.0
    converged = False
    iterations = 0
    last_step = 0.0

    for k in range(1, max_iter + 1):
        iterations = k
        g = gradient(theta, responses)
        h = hessian(theta, responses)

        # Non-concave (h >= 0, shouldn't happen with a_i > 0) — fall back
        # to a small gradient-descent step in the -sign(g) direction with
        # magnitude clamped to 0.1. Otherwise take the Newton step.
        # |step| <= 0.1 keeps θ bounded to keep this safe.
        step = (
            (0.0 if g == 0.0 else (-0.1 if g > 0 else 0.1))
            if h >= 0.0
            else g / h  # h < 0, so g/h has the right sign
        )

        new_theta = theta - step
        # Bound to plausible θ range.
        if new_theta > THETA_BOUND:
            new_theta = THETA_BOUND
        elif new_theta < -THETA_BOUND:
            new_theta = -THETA_BOUND

        last_step = abs(new_theta - theta)
        theta = new_theta

        if last_step < tol:
            converged = True
            break

    # Standard error from observed information at θ̂.
    # Information is non-positive (or zero) — infinite SE.
    h_at_hat = hessian(theta, responses)
    standard_error = (
        1.0 / math.sqrt(-h_at_hat) if h_at_hat < 0.0 else float("inf")
    )

    return ThetaResult(
        theta=theta,
        standard_error=standard_error,
        n_items=n_items,
        converged=converged,
        iterations=iterations,
    )


__all__ = [
    "DEFAULT_MAX_ITER",
    "DEFAULT_TOL",
    "THETA_BOUND",
    "ThetaResult",
    "estimate_theta_mle",
    "gradient",
    "hessian",
    "log_likelihood",
    "probability_2pl",
]
