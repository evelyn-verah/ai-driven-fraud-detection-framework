"""Command-line builder for the dashboard's versioned metadata sidecar."""
from .config import METADATA_INDEX_PATH, PAYSIM_RAW_PATH
from .data_access import load_score_cache
from .metadata_index import build_metadata_index


def main() -> None:
    result = build_metadata_index(PAYSIM_RAW_PATH, load_score_cache(), METADATA_INDEX_PATH)
    print(f"published {result.directory} ({len(result.frame):,} rows)")


if __name__ == "__main__":
    main()
