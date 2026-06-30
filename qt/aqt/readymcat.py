# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""ReadyMCAT honest-memory dashboard window.

Hosts the Svelte `readymcat-dashboard` page, which consumes the points-at-stake
backend message (per-topic mastery/weakness, the ranged memory score and the
coverage map, obeying the give-up rule)."""

from __future__ import annotations

import os
from urllib.parse import quote

import aqt.main
from aqt.qt import QDialog, Qt, QVBoxLayout
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind


class ReadyMCATDashboard(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        super().__init__(mw, Qt.WindowType.Window)
        self.mw = mw
        self.name = "readyMCATDashboard"
        mw.garbage_collect_on_dialog_finish(self)
        self.setWindowTitle("ReadyMCAT — Honest Memory")
        self.setMinimumSize(720, 720)
        disable_help_button(self)
        restoreGeom(self, self.name, default_size=(820, 820))

        self.web = AnkiWebView(self, kind=AnkiWebViewKind.READYMCAT_DASHBOARD)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)

        self.web.load_sveltekit_page(self._page_path())
        self.show()

    def _page_path(self) -> str:
        page = "readymcat-dashboard"
        taxonomy = _bundled_taxonomy_path(self.mw)
        if taxonomy:
            return f"{page}?taxonomy={quote(taxonomy)}"
        return page

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd == "close":
            self.close()
        return False

    def reject(self) -> None:
        if self.web:
            self.web.cleanup()
            self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def _bundled_taxonomy_path(mw: aqt.main.AnkiQt) -> str:
    """Locate a taxonomy.json.

    Prefer one next to the collection (the backend finds that itself, so we
    return ""); otherwise fall back to a stub in the working directory, which is
    handy for `just run` development builds."""
    if mw.col is not None:
        col_dir = os.path.dirname(mw.col.path)
        if os.path.exists(os.path.join(col_dir, "taxonomy.json")):
            return ""
    candidate = os.path.join(os.getcwd(), "taxonomy.json")
    if os.path.exists(candidate):
        return candidate
    return ""


def show_readymcat_dashboard(mw: aqt.main.AnkiQt) -> None:
    ReadyMCATDashboard(mw)
