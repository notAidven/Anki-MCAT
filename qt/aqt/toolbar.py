# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
from __future__ import annotations

import enum
import json
import re
from collections.abc import Callable
from typing import Any, cast

import aqt
from anki.sync import SyncStatus
from aqt import gui_hooks, props
from aqt.qt import *
from aqt.sync import get_sync_status
from aqt.theme import theme_manager
from aqt.utils import tr
from aqt.webview import AnkiWebView, AnkiWebViewKind


class HideMode(enum.IntEnum):
    FULLSCREEN = 0
    ALWAYS = 1


# wrapper class for set_bridge_command()
class TopToolbar:
    def __init__(self, toolbar: Toolbar) -> None:
        self.toolbar = toolbar


# wrapper class for set_bridge_command()
class BottomToolbar:
    def __init__(self, toolbar: Toolbar) -> None:
        self.toolbar = toolbar


class ToolbarWebView(AnkiWebView):
    hide_condition: Callable[..., bool]

    def __init__(
        self, mw: aqt.AnkiQt, kind: AnkiWebViewKind = AnkiWebViewKind.DEFAULT
    ) -> None:
        AnkiWebView.__init__(self, mw, kind=kind)
        self.mw = mw
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.disable_zoom()
        self.hidden = False
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.reset_timer()

    def reset_timer(self) -> None:
        self.hide_timer.stop()
        self.hide_timer.setInterval(2000)

    def hide(self) -> None:
        self.hidden = True

    def show(self) -> None:
        self.hidden = False


class TopWebView(ToolbarWebView):
    def __init__(self, mw: aqt.AnkiQt) -> None:
        super().__init__(mw, kind=AnkiWebViewKind.TOP_TOOLBAR)
        self.web_height = 0
        qconnect(self.hide_timer.timeout, self.hide_if_allowed)

    def eventFilter(self, obj, evt):
        if handled := super().eventFilter(obj, evt):
            return handled

        # prevent collapse of both toolbars if pointer is inside one of them
        if evt.type() == QEvent.Type.Enter:
            self.reset_timer()
            self.mw.bottomWeb.reset_timer()
            return True

        return False

    def on_body_classes_need_update(self) -> None:
        super().on_body_classes_need_update()

        if self.mw.state == "review":
            if self.mw.pm.hide_top_bar():
                self.eval("""document.body.classList.remove("flat"); """)
            else:
                self.flatten()

        self.adjustHeightToFit()
        self.show()

    def _onHeight(self, qvar: int | None) -> None:
        super()._onHeight(qvar)
        if qvar:
            self.web_height = int(qvar)

    def hide_if_allowed(self) -> None:
        if self.mw.state != "review":
            return

        # Invariant: The `hide_if_allowed` method ensures that the fullscreen state is checked
        # and the menubar will be hidden if necessary
        # Note: The `eventFilter` and `_reviewState` methods in `qt/aqt/main.py` rely on this invariant
        if self.mw.fullscreen:
            self.mw.hide_menubar()

        if self.mw.pm.hide_top_bar():
            if (
                self.mw.pm.top_bar_hide_mode() == HideMode.FULLSCREEN
                and not self.mw.windowState() & Qt.WindowState.WindowFullScreen
            ):
                self.show()
                return

            self.hide()

    def hide(self) -> None:
        super().hide()

        self.hidden = True
        self.eval(
            """document.body.classList.add("hidden"); """,
        )

    def show(self) -> None:
        super().show()

        self.eval("""document.body.classList.remove("hidden"); """)

    def flatten(self) -> None:
        self.eval("""document.body.classList.add("flat"); """)

    def elevate(self) -> None:
        self.eval(
            """
            document.body.classList.remove("flat");
            document.body.style.removeProperty("background");
            """
        )

    def update_background_image(self) -> None:
        if self.mw.pm.minimalist_mode():
            return

        def set_background(computed: str) -> None:
            # remove offset from copy
            background = re.sub(r"-\d+px ", "0%", computed)
            # ensure alignment with main webview
            background = re.sub(r"\sfixed", "", background)
            # change computedStyle px value back to 100vw
            background = re.sub(r"\d+px", "100vw", background)

            self.eval(
                f"""
                    document.body.style.setProperty("background", '{background}');
                """
            )
            self.set_body_height(self.mw.web.height())

            # offset reviewer background by toolbar height
            if self.web_height:
                self.mw.web.eval(
                    f"""document.body.style.setProperty("background-position-y", "-{self.web_height}px"); """
                )

        self.mw.web.evalWithCallback(
            """window.getComputedStyle(document.body).background; """,
            set_background,
        )

    def set_body_height(self, height: int) -> None:
        self.eval(
            f"""document.body.style.setProperty("min-height", "{self.mw.web.height()}px"); """
        )

    def adjustHeightToFit(self) -> None:
        self.eval("""document.body.style.setProperty("min-height", "0px"); """)
        self.evalWithCallback("document.documentElement.offsetHeight", self._onHeight)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)

        self.mw.web.evalWithCallback(
            """window.innerHeight; """,
            self.set_body_height,
        )


class BottomWebView(ToolbarWebView):
    def __init__(self, mw: aqt.AnkiQt) -> None:
        super().__init__(mw, kind=AnkiWebViewKind.BOTTOM_TOOLBAR)
        qconnect(self.hide_timer.timeout, self.hide_if_allowed)

    def eventFilter(self, obj, evt):
        if handled := super().eventFilter(obj, evt):
            return handled

        if evt.type() == QEvent.Type.Enter:
            self.reset_timer()
            self.mw.toolbarWeb.reset_timer()
            return True

        return False

    def on_body_classes_need_update(self) -> None:
        super().on_body_classes_need_update()
        if self.mw.state == "review":
            self.show()

    def animate_height(self, height: int) -> None:
        self.web_height = height

        if self.mw.pm.reduce_motion() or height == self.height():
            self.setFixedHeight(height)
        else:
            # Collapse/Expand animation
            self.setMinimumHeight(0)
            self.animation = QPropertyAnimation(
                self, cast(QByteArray, b"maximumHeight")
            )
            self.animation.setDuration(int(theme_manager.var(props.TRANSITION)))
            self.animation.setStartValue(self.height())
            self.animation.setEndValue(height)
            qconnect(self.animation.finished, lambda: self.setFixedHeight(height))
            self.animation.start()

    def hide_if_allowed(self) -> None:
        if self.mw.state != "review":
            return

        if self.mw.pm.hide_bottom_bar():
            if (
                self.mw.pm.bottom_bar_hide_mode() == HideMode.FULLSCREEN
                and not self.mw.windowState() & Qt.WindowState.WindowFullScreen
            ):
                self.show()
                return

            self.hide()

    def hide(self) -> None:
        super().hide()

        self.hidden = True
        self.animate_height(1)

    def show(self) -> None:
        super().show()

        self.hidden = False
        if self.mw.state == "review":
            # delay to account for reflow
            def cb(height: int | None):
                # "When QWebEnginePage is deleted, the callback is triggered with an invalid value"
                if height is not None:
                    self.animate_height(height)

            self.mw.progress.single_shot(
                50,
                lambda: self.evalWithCallback(
                    "document.documentElement.offsetHeight", cb
                ),
                False,
            )
        else:
            self.adjustHeightToFit()


class Toolbar:
    def __init__(self, mw: aqt.AnkiQt, web: AnkiWebView) -> None:
        self.mw = mw
        self.web = web
        self.link_handlers: dict[str, Callable] = {
            "study": self._studyLinkHandler,
        }
        self.web.requiresCol = False

    def draw(
        self,
        buf: str = "",
        web_context: Any | None = None,
        link_handler: Callable[[str], Any] | None = None,
    ) -> None:
        web_context = web_context or TopToolbar(self)
        link_handler = link_handler or self._linkHandler
        self.web.set_bridge_command(link_handler, web_context)
        # ReadyMCAT: the centre of the toolbar is the persistent single-window
        # tab bar (Home · Study · Decks · Dashboard); the standard Anki
        # utilities (Add / Browse / Stats / Sync) move to the right tray so they
        # stay one click away without competing with the tabs.
        body = self._body.format(
            toolbar_content=self._readymcat_tabs(),
            left_tray_content=self._left_tray_content(),
            right_tray_content=self._utility_links() + self._right_tray_content(),
        )
        self.web.stdHtml(
            body,
            css=["css/toolbar.css"],
            js=["js/vendor/jquery.min.js", "js/toolbar.js"],
            context=web_context,
        )
        self.web.adjustHeightToFit()
        self.set_active_tab(self.mw.state)

    def redraw(self) -> None:
        self.set_sync_active(self.mw.media_syncer.is_syncing())
        self.update_sync_status()
        self.set_active_tab(self.mw.state)
        gui_hooks.top_toolbar_did_redraw(self)

    # ReadyMCAT single-window tab bar
    ######################################################################

    def _readymcat_tabs(self) -> str:
        """The persistent Home · Study · Decks · Dashboard tab bar.

        Rendered as the toolbar's centred primary navigation so all four
        ReadyMCAT surfaces live in one window. Active state is refreshed from
        the main-window state on every ``moveToState`` / redraw (see
        ``set_active_tab``)."""
        tabs = [
            self._create_tab("home", "Home", self._homeTabHandler),
            self._create_tab("study", "Study", self._studyTabHandler),
            self._create_tab("decks", tr.actions_decks(), self._deckLinkHandler),
            self._create_tab("dashboard", "Dashboard", self._dashboardTabHandler),
        ]
        return f"""<div class="rmcat-tabs" role="tablist">{"".join(tabs)}</div>"""

    def _create_tab(self, tab_id: str, label: str, func: Callable) -> str:
        """Generate one tab link and register its bridge handler."""
        cmd = f"rmcatTab:{tab_id}"
        self.link_handlers[cmd] = func
        return (
            f'<a class="hitem rmcat-tab" data-rmcat-tab="{tab_id}" '
            f'id="rmcat-tab-{tab_id}" role="tab" aria-selected="false" '
            f'tabindex="-1" aria-label="{label}" href=# '
            f"onclick=\"return pycmd('{cmd}')\">{label}</a>"
        )

    def set_active_tab(self, state: str) -> None:
        """Highlight the tab matching the current main-window ``state`` (or none
        for transient states like the profile manager)."""
        tab = {
            "deckBrowser": "decks",
            "overview": "study",
            "review": "study",
            "readymcatHome": "home",
            "readymcatDashboard": "dashboard",
        }.get(state, "")
        self.web.eval(
            "(function(){var t=%s;"
            "document.querySelectorAll('.rmcat-tab').forEach(function(el){"
            "var on=el.dataset.rmcatTab===t;"
            "el.classList.toggle('active',on);"
            "el.setAttribute('aria-selected',on?'true':'false');});})();"
            % json.dumps(tab)
        )

    def _homeTabHandler(self) -> None:
        self.mw.moveToState("readymcatHome")

    def _dashboardTabHandler(self) -> None:
        self.mw.moveToState("readymcatDashboard")

    def _studyTabHandler(self) -> None:
        # Go straight into the reviewer for the currently-selected deck in a
        # single load (a double moveToState races the reviewer's paint — see
        # aqt.readymcat_home._start_review_now). The reviewer falls back to the
        # deck overview / congrats screen on its own when nothing is due.
        if self.mw.state == "review":
            return
        if self.mw.col is not None:
            self.mw.col.startTimebox()
        self.mw.moveToState("review")

    def _utility_links(self) -> str:
        """The standard Add / Browse / Stats / Sync links, shown in the right
        tray now that the toolbar centre hosts the ReadyMCAT tab bar."""
        links = [
            self.create_link(
                "add",
                tr.actions_add(),
                self._addLinkHandler,
                tip=tr.actions_shortcut_key(val="A"),
                id="add",
            ),
            self.create_link(
                "browse",
                tr.qt_misc_browse(),
                self._browseLinkHandler,
                tip=tr.actions_shortcut_key(val="B"),
                id="browse",
            ),
            self.create_link(
                "stats",
                tr.qt_misc_stats(),
                self._statsLinkHandler,
                tip=tr.actions_shortcut_key(val="T"),
                id="stats",
            ),
            self._create_sync_link(),
        ]

        gui_hooks.top_toolbar_did_init_links(links, self)

        return "\n".join(links)

    # Available links
    ######################################################################

    def create_link(
        self,
        cmd: str,
        label: str,
        func: Callable,
        tip: str | None = None,
        id: str | None = None,
    ) -> str:
        """Generates HTML link element and registers link handler

        Arguments:
            cmd {str} -- Command name used for the JS → Python bridge
            label {str} -- Display label of the link
            func {Callable} -- Callable to be called on clicking the link

        Keyword Arguments:
            tip {Optional[str]} -- Optional tooltip text to show on hovering
                                   over the link (default: {None})
            id: {Optional[str]} -- Optional id attribute to supply the link with
                                   (default: {None})

        Returns:
            str -- HTML link element
        """

        self.link_handlers[cmd] = func

        title_attr = f'title="{tip}"' if tip else ""
        id_attr = f'id="{id}"' if id else ""

        return (
            f"""<a class=hitem tabindex="-1" aria-label="{label}" """
            f"""{title_attr} {id_attr} href=# onclick="return pycmd('{cmd}')">"""
            f"""{label}</a>"""
        )

    def _centerLinks(self) -> str:
        links = [
            self.create_link(
                "decks",
                tr.actions_decks(),
                self._deckLinkHandler,
                tip=tr.actions_shortcut_key(val="D"),
                id="decks",
            ),
            self.create_link(
                "add",
                tr.actions_add(),
                self._addLinkHandler,
                tip=tr.actions_shortcut_key(val="A"),
                id="add",
            ),
            self.create_link(
                "browse",
                tr.qt_misc_browse(),
                self._browseLinkHandler,
                tip=tr.actions_shortcut_key(val="B"),
                id="browse",
            ),
            self.create_link(
                "stats",
                tr.qt_misc_stats(),
                self._statsLinkHandler,
                tip=tr.actions_shortcut_key(val="T"),
                id="stats",
            ),
        ]

        links.append(self._create_sync_link())

        gui_hooks.top_toolbar_did_init_links(links, self)

        return "\n".join(links)

    # Add-ons
    ######################################################################

    def _left_tray_content(self) -> str:
        left_tray_content: list[str] = []
        gui_hooks.top_toolbar_will_set_left_tray_content(left_tray_content, self)
        return self._process_tray_content(left_tray_content)

    def _right_tray_content(self) -> str:
        right_tray_content: list[str] = []
        gui_hooks.top_toolbar_will_set_right_tray_content(right_tray_content, self)
        return self._process_tray_content(right_tray_content)

    def _process_tray_content(self, content: list[str]) -> str:
        return "\n".join(f"""<div class="tray-item">{item}</div>""" for item in content)

    # Sync
    ######################################################################

    def _create_sync_link(self) -> str:
        name = tr.qt_misc_sync()
        title = tr.actions_shortcut_key(val="Y")
        label = "sync"
        self.link_handlers[label] = self._syncLinkHandler

        return f"""
<a class=hitem tabindex="-1" aria-label="{name}" title="{title}" id="{label}" href=# onclick="return pycmd('{label}')"
>{name}<img id=sync-spinner src='/_anki/imgs/refresh.svg'>
</a>"""

    def set_sync_active(self, active: bool) -> None:
        method = "add" if active else "remove"
        self.web.eval(
            f"document.getElementById('sync-spinner').classList.{method}('spin')"
        )

    def set_sync_status(self, status: SyncStatus) -> None:
        self.web.eval(f"updateSyncColor({status.required})")

    def update_sync_status(self) -> None:
        get_sync_status(self.mw, self.mw.toolbar.set_sync_status)

    # Link handling
    ######################################################################

    def _linkHandler(self, link: str) -> bool:
        if link in self.link_handlers:
            self.link_handlers[link]()
        return False

    def _deckLinkHandler(self) -> None:
        self.mw.moveToState("deckBrowser")

    def _studyLinkHandler(self) -> None:
        # if overview already shown, switch to review
        if self.mw.state == "overview":
            self.mw.col.startTimebox()
            self.mw.moveToState("review")
        else:
            self.mw.onOverview()

    def _addLinkHandler(self) -> None:
        self.mw.onAddCard()

    def _browseLinkHandler(self) -> None:
        self.mw.onBrowse()

    def _statsLinkHandler(self) -> None:
        self.mw.onStats()

    def _syncLinkHandler(self) -> None:
        self.mw.on_sync_button_clicked()

    # HTML & CSS
    ######################################################################

    _body = """
<div class="header">
  <div class="left-tray">{left_tray_content}</div>
  <div class="toolbar">{toolbar_content}</div>
  <div class="right-tray">{right_tray_content}</div>
</div>
"""


# Bottom bar
######################################################################


class BottomBar(Toolbar):
    _centerBody = """
<center id=outer><table width=100%% id=header><tr><td align=center>
%s</td></tr></table></center>
"""

    def draw(
        self,
        buf: str = "",
        web_context: Any | None = None,
        link_handler: Callable[[str], Any] | None = None,
    ) -> None:
        # note: some screens may override this
        web_context = web_context or BottomToolbar(self)
        link_handler = link_handler or self._linkHandler
        self.web.set_bridge_command(link_handler, web_context)
        self.web.stdHtml(
            self._centerBody % buf,
            css=["css/toolbar.css", "css/toolbar-bottom.css"],
            context=web_context,
        )
        self.web.adjustHeightToFit()
