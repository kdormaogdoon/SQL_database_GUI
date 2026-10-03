"""Statistical distributions that can be assigned to player attributes."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Normal:
    mean: float
    std: float
    kind = "normal"
    param_names = ("mean", "std")

    def sample(self, rng=random):
        return rng.gauss(self.mean, self.std)

    def params(self):
        return {"mean": self.mean, "std": self.std}


@dataclass(frozen=True)
class Uniform:
    low: float
    high: float
    kind = "uniform"
    param_names = ("low", "high")

    def sample(self, rng=random):
        return rng.uniform(self.low, self.high)

    def params(self):
        return {"low": self.low, "high": self.high}


@dataclass(frozen=True)
class Triangular:
    low: float
    mode: float
    high: float
    kind = "triangular"
    param_names = ("low", "mode", "high")

    def sample(self, rng=random):
        return rng.triangular(self.low, self.high, self.mode)

    def params(self):
        return {"low": self.low, "mode": self.mode, "high": self.high}


DISTRIBUTIONS = {"normal": Normal, "uniform": Uniform, "triangular": Triangular}


def from_spec(kind, **params):
    """Build a distribution from its name and keyword parameters."""
    try:
        cls = DISTRIBUTIONS[kind]
    except KeyError:
        raise ValueError(f"unknown distribution {kind!r}; choose from {sorted(DISTRIBUTIONS)}")
    dist = cls(**{k: float(v) for k, v in params.items()})
    if kind == "normal" and dist.std < 0:
        raise ValueError("std must be >= 0")
    if kind == "uniform" and dist.low > dist.high:
        raise ValueError("low must be <= high")
    if kind == "triangular" and not dist.low <= dist.mode <= dist.high:
        raise ValueError("require low <= mode <= high")
    return dist


def default_for(lo, hi, kind="normal"):
    """Sensible default parameters for an attribute with range [lo, hi]."""
    mid = (lo + hi) / 2
    if kind == "normal":
        return Normal(mid, (hi - lo) / 6)
    if kind == "uniform":
        return Uniform(lo, hi)
    return Triangular(lo, mid, hi)
