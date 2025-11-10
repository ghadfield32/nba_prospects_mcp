"""College & International Basketball Dataset Puller

A unified API for accessing college basketball (NCAA Men's & Women's)
and international basketball data (EuroLeague, FIBA, NBL, etc.)
"""

from .api.datasets import get_dataset, list_datasets

__version__ = "0.1.0"
__all__ = ["get_dataset", "list_datasets"]
