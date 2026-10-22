"""Module 6 V1.2 secure Streamlit launcher.

The historical V1/V1.1 dashboard source is preserved under the recorded
artifact snapshot. Supported launches now delegate to the fail-closed secure
entry point; no user-controlled role or URL value creates identity.
"""

from __future__ import annotations


def _running_under_streamlit() -> bool:
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    return get_script_run_ctx() is not None


def main() -> None:
    """Launch the secure dashboard; deny access when no trusted identity exists."""
    if not _running_under_streamlit():
        print("Protected dashboard access is denied outside Streamlit.")
        return

    try:
        from src.dashboard.secure_app import streamlit_main
    except ModuleNotFoundError:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.dashboard.secure_app import streamlit_main

    streamlit_main()


if __name__ == "__main__":
    main()
