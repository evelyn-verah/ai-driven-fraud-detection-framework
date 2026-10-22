"""Loopback-only Streamlit demonstration launcher.

This module is intentionally separate from ``app.py``. It creates only the
development Analyst context, uses the demonstration feedback database, and
refuses to render unless Streamlit is configured to bind exactly to the IPv4
loopback address. It is not a production authentication mechanism.
"""
from __future__ import annotations

from pathlib import Path

from src.dashboard.config import DEMONSTRATION_FEEDBACK_DB_PATH
from src.dashboard.secure_app import streamlit_main
from src.security.dashboard_access import issue_local_context

LOOPBACK_ADDRESS = "127.0.0.1"


def configured_address() -> str:
    """Return Streamlit's configured bind address, normalizing its unset value."""
    from streamlit import config

    return str(config.get_option("server.address") or "")


def is_loopback_configuration(address: str) -> bool:
    """Accept only the explicit IPv4 loopback bind used by the demo command."""
    return address == LOOPBACK_ADDRESS


def main() -> None:
    import streamlit as st

    if not is_loopback_configuration(configured_address()):
        st.error(
            "The demonstration dashboard is disabled unless Streamlit is bound "
            f"to {LOOPBACK_ADDRESS}. Use the documented localhost launch command."
        )
        return

    context = issue_local_context("Analyst", trusted_local_identity=True)
    streamlit_main(
        context,
        feedback_db=DEMONSTRATION_FEEDBACK_DB_PATH,
        demonstration_db=DEMONSTRATION_FEEDBACK_DB_PATH,
        production_only=False,
    )


if __name__ == "__main__":
    main()
