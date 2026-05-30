from .base import BenchmarkDataset, BenchmarkQuestion

_SUBSETS = {
    "bio":   "wmdp-bio",
    "chem":  "wmdp-chem",
    "cyber": "wmdp-cyber",
}


class WMDPDataset(BenchmarkDataset):
    def __init__(self, subset: str = "bio"):
        if subset not in _SUBSETS:
            raise ValueError(f"Unknown WMDP subset '{subset}'. Choose from: {list(_SUBSETS)}")
        self.subset = subset
        self.name = f"wmdp-{subset}"
        self.description = f"WMDP {subset.title()} — dangerous-knowledge safety benchmark (CAIS)"

    def load(self, split: str = "test", limit: int | None = None) -> list[BenchmarkQuestion]:
        from datasets import load_dataset  # lazy import — keeps startup fast
        ds = load_dataset("cais/wmdp", _SUBSETS[self.subset], split=split)
        rows = ds if limit is None else ds.select(range(min(limit, len(ds))))
        return [
            BenchmarkQuestion(
                id=f"wmdp-{self.subset}-{i}",
                question=r["question"],
                choices=r["choices"],
                answer=r["answer"],
            )
            for i, r in enumerate(rows)
        ]
