import sublime

from .configurations import is_supported_syntax
from .registry import LSPViewEventListener
from .settings import client_configs
from .typing import Optional


SUBLIME_WORD_MASK = 515


def get_position(view: sublime.View, event: Optional[dict] = None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


def is_at_word(view: sublime.View, event: Optional[dict]) -> bool:
    pos = get_position(view, event)
    return position_is_word(view, pos)


def position_is_word(view: sublime.View, position: int) -> bool:
    point_classification = view.classify(position)
    if point_classification & SUBLIME_WORD_MASK:
        return True
    else:
        return False


def is_transient_view(view: sublime.View) -> bool:
    window = view.window()
    if window:
        if window.get_view_index(view)[1] == -1:
            return True  # Quick panel transient views
        return view == window.transient_view_in_group(window.active_group())
    else:
        return True


class DocumentSyncListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    @classmethod
    def is_applicable(cls, settings: dict) -> bool:
        syntax = settings.get('syntax')  # type: 'Optional[str]'
        # This enables all of document sync for any supportable syntax
        # Global performance cost, consider a detect_lsp_support setting
        if not syntax:
            return False
        else:
            return is_supported_syntax(syntax, client_configs.all)

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def on_load_async(self) -> None:
        # skip transient views:
        if not is_transient_view(self.view):
            self.manager.activate_view(self.view)
            self.manager.documents.handle_did_open(self.view)

    def on_activated_async(self) -> None:
        if self.view.file_name() and not is_transient_view(self.view):
            self.manager.activate_view(self.view)
            self.manager.documents.handle_did_open(self.view)

    def on_modified(self) -> None:
        if self.view.file_name():
            self.manager.documents.handle_did_change(self.view)

    def on_pre_save(self) -> None:
        if self.view.file_name():
            self.manager.documents.handle_will_save(self.view, reason=1)  # TextDocumentSaveReason.Manual

    def on_post_save_async(self) -> None:
        self.manager.documents.handle_did_save(self.view)

    def on_close(self) -> None:
        if self.view.file_name() and self.view.is_primary() and self.has_manager():
            self.manager.handle_view_closed(self.view)
            self.manager.documents.handle_did_close(self.view)
