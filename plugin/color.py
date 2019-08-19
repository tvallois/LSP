import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional
    assert Any and List and Dict and Callable and Optional
except ImportError:
    pass

from .core.protocol import Request
from .core.url import filename_to_uri
from .core.registry import session_for_view
from .core.settings import settings
from .core.views import range_to_region
from .core.protocol import Range


def send_color_request(view, on_response_recieved: 'Callable'):
    session = session_for_view(view)
    if not session or not session.has_capability('colorProvider'):
        # the server doesn't support colors, just return
        return

    params = {
        "textDocument": {
            "uri": filename_to_uri(view.file_name())
        }
    }
    session.client.send_request(
        Request.color(params),
        lambda response: on_response_recieved(response))


color_phantom_sets_by_id = {}  # type: Dict[int, sublime.PhantomSet]


class LspColorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_point = -1

    @classmethod
    def is_applicable(cls, _settings):
        if settings.show_color_box:
            return True
        return False

    def on_activated_async(self):
        self.schedule_request()

    def on_modified_async(self):
        self.schedule_request()

    def schedule_request(self):
        current_point = self.view.sel()[0].begin()
        if self._stored_point != current_point:
            self._stored_point = current_point
            sublime.set_timeout_async(lambda: self.fire_request(current_point), 800)

    def fire_request(self, current_point: int) -> None:
        if current_point == self._stored_point:
            send_color_request(self.view, self.handle_response)

    def handle_response(self, response) -> None:
        global color_phantom_sets_by_id
        id = self.view.id()

        phantoms = []
        for val in response:
            color = val['color']
            red = color['red'] * 255
            green = color['green'] * 255
            blue = color['blue'] * 255
            alpha = color['alpha']

            content = """
            <div style='padding: 0.5rem;
                        margin-top: 0.1rem;
                        border: 1px solid color(var(--foreground) alpha(0.25));
                        background-color: rgba({}, {}, {}, {})'>
            </div>""".format(red, green, blue, alpha)

            range = Range.from_lsp(val['range'])
            region = range_to_region(range, self.view)

            phantoms.append(sublime.Phantom(region, content, sublime.LAYOUT_INLINE))

        if phantoms:
            phantom_set = color_phantom_sets_by_id.get(id)
            if not phantom_set:
                phantom_set = sublime.PhantomSet(self.view, "lsp_color")
                color_phantom_sets_by_id[id] = phantom_set
            phantom_set.update(phantoms)
        else:
            color_phantom_sets_by_id.pop(id, None)


def remove_color_boxes(view):
    view.erase_phantoms('lsp_color')
