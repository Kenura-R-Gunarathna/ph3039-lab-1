#!/usr/bin/env python3
"""Terminal UI for recording a voice dataset from the XIAO nRF52840 Sense (apps/audio_capture).

    pixi run tui            (or: python tools/dataset_tui.py [--port /dev/cu.usbmodemXXXX])

Left: words (and the reserved `noise` class).  Right: clips of the selected word + waveform.
Keys are listed in the footer.  Files and layout are the same as tools/dataset_cli.py.
"""
import argparse, os, sys, time

import numpy as np
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset_cli as ds

BLOCKS = " ▁▂▃▄▅▆▇█"


def wave_text(x, width, height):
    """Bar-chart envelope of |x| as block characters, `height` rows tall."""
    if x is None or width < 4 or height < 1:
        return Text("")
    ac = x.astype(float) - x.mean()
    cols = np.array_split(np.abs(ac), width)
    amp = np.array([c.max() if len(c) else 0 for c in cols])
    scale = max(float(amp.max()), 1000.0)
    eighths = (amp / scale * height * 8).astype(int)
    peak = int(np.abs(x).max())
    colour = "red" if peak > 32000 else "green"
    rows = []
    for r in range(height - 1, -1, -1):
        rows.append("".join(BLOCKS[int(np.clip(e - r * 8, 0, 8))] for e in eighths))
    t = Text("\n".join(rows), style=colour)
    return t


class Prompt(ModalScreen):
    CSS = """
    Prompt { align: center middle; }
    #box { width: 50; height: auto; border: round $accent; background: $surface; padding: 1 2; }
    """

    def __init__(self, title, default=""):
        super().__init__()
        self.title_text, self.default = title, default

    def compose(self):
        with Vertical(id="box"):
            yield Label(self.title_text)
            yield Input(value=self.default, id="field")
            yield Label("[dim]Enter = ok   Esc = cancel[/dim]")

    @on(Input.Submitted)
    def _ok(self, event):
        self.dismiss(event.value.strip())

    def key_escape(self):
        self.dismiss(None)


class Confirm(ModalScreen):
    CSS = """
    Confirm { align: center middle; }
    #box { width: 56; height: auto; border: round $error; background: $surface; padding: 1 2; }
    """
    BINDINGS = [("y", "yes", "Yes"), ("n,escape", "no", "No")]

    def __init__(self, text):
        super().__init__()
        self.text = text

    def compose(self):
        with Vertical(id="box"):
            yield Label(self.text)
            yield Label("[dim]y = yes   n = no[/dim]")

    def action_yes(self):
        self.dismiss(True)

    def action_no(self):
        self.dismiss(False)


class DatasetApp(App):
    TITLE = "Voice dataset"
    CSS = """
    #words { width: 28; height: 100%; border: round $primary; }
    #right { width: 1fr; }
    #clips { height: 1fr; border: round $primary; }
    #wave { height: 11; border: round $primary; padding: 0 1; }
    #status { height: 4; border: round $secondary; padding: 0 1; }
    OptionList:focus, DataTable:focus { border: round $accent; }
    """
    BINDINGS = [
        Binding("space", "record", "Record"),
        Binding("b", "batch", "Batch"),
        Binding("p", "play", "Play"),
        Binding("d", "delete_clip", "Del clip"),
        Binding("n", "new_word", "New word"),
        Binding("e", "rename_word", "Rename"),
        Binding("x", "delete_word", "Del word"),
        Binding("a", "toggle_autoplay", "Autoplay"),
        Binding("u", "augment", "Augment"),
        Binding("tab", "focus_next", "Switch pane", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, port=None):
        super().__init__()
        self.board = ds.Board(port)
        self.label = None
        self.autoplay = True
        self.busy = False
        self.current_clip = None            # samples shown in the waveform

    # ----- layout -----
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield OptionList(id="words")
            with Vertical(id="right"):
                yield DataTable(id="clips", cursor_type="row", zebra_stripes=True)
                yield Static(id="wave")
                yield Static(id="status")
        yield Footer()

    def on_mount(self):
        self.query_one("#words").border_title = "Words"
        self.query_one("#clips").border_title = "Clips"
        self.query_one("#wave").border_title = "Waveform"
        self.query_one("#status").border_title = "Status"
        self.query_one("#clips", DataTable).add_columns("#", "file", "peak", "rms", "")
        os.makedirs(f"{ds.DATA}/{ds.NOISE}", exist_ok=True)
        self.refresh_words()
        self.query_one("#words").focus()
        self.set_status("Connecting to board ...")
        self.run_worker(self._connect, thread=True)

    def _connect(self):
        ok = self.board.connect()
        self.call_from_thread(self.set_status, f"Board ready on {self.board.port}.  Space = record." if ok
                              else "Board not found - plug it in; it will retry when you record.")

    def on_resize(self, event):
        self.draw_wave()

    # ----- helpers -----
    def set_status(self, msg):
        autoplay = "on" if self.autoplay else "off"
        self.query_one("#status", Static).update(f"{msg}\n[dim]autoplay: {autoplay}[/dim]")

    def all_labels(self):
        return ds.labels() + [ds.NOISE]

    def refresh_words(self, select=None):
        ol = self.query_one("#words", OptionList)
        names = self.all_labels()
        ol.clear_options()
        ol.add_options([Option(f"{n}  ({len(ds.clips_of(n))})" + ("  *noise*" if n == ds.NOISE else ""), id=n)
                        for n in names])
        target = select or self.label or names[0]
        ol.highlighted = names.index(target) if target in names else 0

    def refresh_clips(self, keep=None):
        table = self.query_one("#clips", DataTable)
        table.clear()
        self.query_one("#clips").border_title = f"Clips - {self.label}" if self.label else "Clips"
        for i, path in enumerate(ds.clips_of(self.label) if self.label else [], 1):
            x = ds.read_wav(path)
            speech = self.label != ds.NOISE
            peak, rms = int(np.abs(x).max()), float(np.std(x.astype(float)))
            flag = "CLIP" if peak > 32000 else "quiet" if speech and peak < 1500 else ""
            table.add_row(str(i), os.path.basename(path), str(peak), f"{rms:.0f}", flag, key=path)
        if table.row_count:
            row = table.row_count - 1
            if keep and keep in [k.value for k in table.rows]:
                row = [k.value for k in table.rows].index(keep)
            table.move_cursor(row=row)
        else:
            self.current_clip = None
            self.draw_wave()

    def highlighted_path(self):
        table = self.query_one("#clips", DataTable)
        if not table.row_count:
            return None
        return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value

    def draw_wave(self):
        w = self.query_one("#wave", Static)
        w.update(wave_text(self.current_clip, w.size.width - 4, max(w.size.height - 2, 1)))

    # ----- selection events -----
    @on(OptionList.OptionHighlighted, "#words")
    def _word_changed(self, event):
        self.label = event.option.id
        self.refresh_clips()

    @on(DataTable.RowHighlighted, "#clips")
    def _clip_changed(self, event):
        if event.row_key is None or event.row_key.value is None:
            return
        self.current_clip = ds.read_wav(event.row_key.value)
        self.draw_wave()

    @on(DataTable.RowSelected, "#clips")
    def _clip_play(self, event):
        self.action_play()

    # ----- recording -----
    def action_record(self):
        self.start_recording(1)

    def action_batch(self):
        if self.busy or not self.label:
            return

        def got(v):
            if v and v.isdigit() and int(v) > 0:
                self.start_recording(min(int(v), 200))
        self.push_screen(Prompt("How many clips in a row?", "10"), got)

    def start_recording(self, count):
        if self.busy or not self.label:
            return
        self.busy = True
        self.run_worker(lambda: self._record_worker(self.label, count), thread=True)

    def _record_worker(self, label, count):
        saved = None
        try:
            for k in range(count):
                tag = f"clip {k + 1}/{count}" if count > 1 else "one clip"
                self.call_from_thread(self.set_status, f"[bold red]● RECORDING[/] {tag} for '{label}' - speak now" if label != ds.NOISE
                                      else f"[bold red]● RECORDING[/] {tag} of background noise")
                try:
                    x = self.board.record()
                except TimeoutError as e:
                    self.call_from_thread(self.set_status, f"[red]Error:[/] {e}")
                    return
                path = f"{ds.DATA}/{label}/{label}_{int(time.time() * 1000)}.wav"
                ds.write_wav(path, x)
                saved = path
                self.call_from_thread(self._clip_saved, label, path, x)
                if count > 1:
                    time.sleep(0.5)
            self.call_from_thread(self.set_status, f"Saved {count} clip(s) to '{label}'.  Space = record again.")
            if self.autoplay and count == 1 and saved:
                ds.play(saved)
        finally:
            self.busy = False

    def _clip_saved(self, label, path, x):
        self.refresh_words(select=label)
        self.refresh_clips(keep=path)
        self.current_clip = x
        self.draw_wave()

    # ----- clips -----
    def action_play(self):
        path = self.highlighted_path()
        if path:
            self.run_worker(lambda: ds.play(path), thread=True, group="play")

    def action_delete_clip(self):
        path = self.highlighted_path()
        if not path or self.busy:
            return
        ds.to_trash(path)
        self.set_status(f"Moved {os.path.basename(path)} to trash.")
        self.refresh_words(select=self.label)

    def action_toggle_autoplay(self):
        self.autoplay = not self.autoplay
        self.set_status("Autoplay " + ("on" if self.autoplay else "off"))

    # ----- words -----
    def action_new_word(self):
        def got(v):
            name = ds.clean_name(v or "")
            if not name or name == ds.NOISE or name in ds.labels():
                if v:
                    self.set_status("[red]Invalid or already existing word.[/]")
                return
            os.makedirs(f"{ds.DATA}/{name}")
            self.refresh_words(select=name)
            self.set_status(f"Created '{name}'.  Space = record.")
        self.push_screen(Prompt("New word"), got)

    def action_rename_word(self):
        old = self.label
        if not old or old == ds.NOISE:
            self.set_status("The noise class can't be renamed.")
            return

        def got(v):
            new = ds.clean_name(v or "")
            if not new or new == ds.NOISE or new in ds.labels():
                if v:
                    self.set_status("[red]Invalid or already existing word.[/]")
                return
            ds.rename_label(old, new)
            self.label = new
            self.refresh_words(select=new)
            self.set_status(f"Renamed '{old}' to '{new}'.")
        self.push_screen(Prompt(f"Rename '{old}' to", old), got)

    def action_delete_word(self):
        old = self.label
        if not old or old == ds.NOISE:
            self.set_status("The noise class can't be deleted.")
            return

        def got(yes):
            if yes:
                ds.to_trash(f"{ds.DATA}/{old}")
                self.label = None
                self.refresh_words()
                self.set_status(f"Moved '{old}' to dataset/_trash/.")
        self.push_screen(Confirm(f"Delete '{old}' and its {len(ds.clips_of(old))} clips?\n(moved to dataset/_trash, reversible)"), got)

    # ----- augmentation -----
    def action_augment(self):
        if not ds.clips_of(ds.NOISE):
            self.set_status("[red]Record some background noise first (select 'noise', press Space).[/]")
            return

        def got(v):
            if v is None:
                return
            k = int(v) if v.isdigit() and int(v) > 0 else 3
            self.set_status(f"Building augmented set ({k} copies per clip) ...")

            def work():
                total = ds.build_augmented(k)
                self.call_from_thread(self.set_status, f"Wrote {total} clips to {ds.AUG}/ "
                                      f"(originals + {k} noise-mixed copies each).")
            self.run_worker(work, thread=True)
        self.push_screen(Prompt("Noise-mixed copies per word clip", "3"), got)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    DatasetApp(ap.parse_args().port).run()


if __name__ == "__main__":
    main()
