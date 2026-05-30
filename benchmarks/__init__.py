from .wmdp import WMDPDataset

# Registry — add new datasets here as one-liners
DATASETS: dict = {
    "wmdp-bio":   lambda: WMDPDataset("bio"),
    "wmdp-chem":  lambda: WMDPDataset("chem"),
    "wmdp-cyber": lambda: WMDPDataset("cyber"),
}
