"""
Chaînes d’interface (fr / en / ar) et résumés de planning localisés.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from core import (
    KIND_AUTHORIZE_WINDOW,
    KIND_BLOCK_ALL,
    KIND_LEGACY_BLOCK_INSIDE,
    KIND_MARKER,
    BlockRule,
    normalize_schedule,
)

SUPPORTED_LOCALES = frozenset({"fr", "en", "ar"})
_DEFAULT_LOCALE = "fr"

_bundle: dict[str, Any] = {}
_current_locale = _DEFAULT_LOCALE


def _base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[arg-type]
    return Path(__file__).resolve().parent


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_locale(code: str) -> dict[str, Any]:
    loc = _base_dir() / "locales"
    base = _load_json(loc / "fr.json")
    if code == "fr":
        return base
    over = _load_json(loc / f"{code}.json")
    merged = dict(base)
    merged.update(over)
    return merged


def normalize_locale(code: str | None) -> str:
    c = str(code or "").strip().lower()[:8]
    if c in SUPPORTED_LOCALES:
        return c
    return _DEFAULT_LOCALE


def current_locale() -> str:
    return _current_locale


def install_locale(code: str, root: Any | None = None) -> str:
    """Charge les traductions et applique la police (Arabic-compatible)."""
    global _bundle, _current_locale
    _current_locale = normalize_locale(code)
    try:
        _bundle = _merge_locale(_current_locale)
    except (OSError, json.JSONDecodeError, TypeError):
        _current_locale = _DEFAULT_LOCALE
        _bundle = _merge_locale(_DEFAULT_LOCALE)
    _apply_ui_fonts(root)
    return _current_locale


def _apply_ui_fonts(root: Any | None) -> None:
    if root is None:
        return
    if not isinstance(root, tk.Misc):
        return
    ui_name = _bundle.get("font_ui") or "Segoe UI"
    mono_name = _bundle.get("font_mono") or "Consolas"
    ui_font = (str(ui_name), 9)
    mono_font = (str(mono_name), 9)
    rtl_ui = bool(_bundle.get("rtl"))
    try:
        style = ttk.Style(root)
        for wname in ("TLabel", "TButton", "TCheckbutton", "TMenubutton"):
            style.configure(wname, font=ui_font)
        tree_kw: dict[str, Any] = {"font": ui_font}
        heading_kw: dict[str, Any] = {"font": ui_font}
        if rtl_ui:
            tree_kw["anchor"] = tk.E
            heading_kw["anchor"] = tk.E
        try:
            f = tkfont.Font(root, family=str(ui_name), size=int(ui_font[1]))
            line_px = max(int(f.metrics("linespace")), 14)
            # Planning : 7 lignes (un jour par ligne).
            tree_kw["rowheight"] = min(7 * line_px + 12, 400)
        except (tk.TclError, TypeError, ValueError):
            tree_kw["rowheight"] = 120
        style.configure("Treeview", **tree_kw)
        style.configure("Treeview.Heading", **heading_kw)
    except tk.TclError:
        pass
    try:
        style = ttk.Style(root)
        style.configure("TCombobox", anchor=tk.E if rtl_ui else tk.W)
    except tk.TclError:
        pass
    try:
        # Liste du menu déroulant (effet selon le thème / plate-forme).
        root.option_add("*TCombobox*Listbox.justify", "right" if rtl_ui else "left")
    except tk.TclError:
        pass
    setattr(root, "_gamefence_ui_font", ui_font)
    setattr(root, "_gamefence_mono_font", mono_font)
    setattr(root, "_gamefence_rtl", bool(_bundle.get("rtl")))


def tr(key: str, **kwargs: Any) -> str:
    raw = _bundle.get(key)
    if isinstance(raw, str):
        if kwargs:
            return raw.format(**kwargs)
        return raw
    return key if not kwargs else str(key).format(**kwargs)


def hotkey_display() -> str:
    return tr("hotkey.display")


def hotkey_keyword() -> str:
    """Nom logique touche finale (pour le hook) — inchangé entre langues."""
    return "g"


def weekday_full(i: int) -> str:
    arr = _bundle.get("weekday_full")
    if isinstance(arr, list) and 0 <= i < len(arr):
        return str(arr[i])
    return str(i)


def weekday_abbr(i: int) -> str:
    arr = _bundle.get("weekday_abbr")
    if isinstance(arr, list) and 0 <= i < len(arr):
        return str(arr[i])
    return str(i)


def mode_labels_tuple() -> tuple[str, ...]:
    return tuple(tr(f"rule.mode_{i}") for i in range(4))


def schedule_summary(rule: BlockRule, max_line_chars: int = 220) -> str:
    """Une ligne par jour (lun→dim), séparées par un saut de ligne pour le tableau."""
    bits: list[str] = []
    sched = normalize_schedule(rule.schedule)
    for d in range(7):
        sl = sched[d]
        abbrev = weekday_abbr(d)
        if sl is None:
            line = f"{abbrev}: {tr('sched.free')}"
        else:
            k = sl.get(KIND_MARKER, "?")
            if k == KIND_BLOCK_ALL:
                line = f"{abbrev}: {tr('sched.block_day')}"
            elif k == KIND_AUTHORIZE_WINDOW:
                line = tr(
                    "sched.fmt_auth",
                    abbr=abbrev,
                    start=sl.get("start", "?"),
                    end=sl.get("end", "?"),
                )
            elif k == KIND_LEGACY_BLOCK_INSIDE:
                line = tr(
                    "sched.fmt_legacy",
                    abbr=abbrev,
                    start=sl.get("start", "?"),
                    end=sl.get("end", "?"),
                )
            else:
                line = tr("sched.unknown", abbr=abbrev)
        if len(line) > max_line_chars:
            line = line[: max_line_chars - 1] + "…"
        bits.append(line)
    return "\n".join(bits)


def ui_font_tuple(root: Any) -> tuple[str, int]:
    f = getattr(root, "_gamefence_ui_font", None)
    if isinstance(f, tuple) and len(f) >= 2:
        return (str(f[0]), int(f[1]))
    return ("Segoe UI", 9)


def mono_font_tuple(root: Any) -> tuple[str, int]:
    f = getattr(root, "_gamefence_mono_font", None)
    if isinstance(f, tuple) and len(f) >= 2:
        return (str(f[0]), int(f[1]))
    return ("Consolas", 9)


def is_rtl() -> bool:
    """Interface en arabo (lecture RTL) : alignement et sens des lignes."""
    return bool(_bundle.get("rtl"))


def tk_justify_paragraph() -> str:
    return tk.RIGHT if is_rtl() else tk.LEFT


def tk_align_text() -> str:
    """Ancrage du bloc de texte (intro, aide, liste)."""
    return tk.E if is_rtl() else tk.W


def rtl_text_embed(s: str) -> str:
    """Tk Text ne gère pas bien le bidi : encadre avec RLE/PDF pour garder l’ordre des mots en arabe."""
    if not is_rtl():
        return s
    t = str(s).replace("\u202b", "").replace("\u202c", "").replace("\u200e", "").replace("\u200f", "")
    return "\u202b" + t + "\u202c"


def attach_rtl_combobox_alignment(cb: ttk.Combobox) -> None:
    """Champ et liste déroulants alignés à droite en arabe (selon thème / Tcl)."""
    if not is_rtl():
        return

    def schedule_list_patch(_event: tk.Event | None = None) -> None:
        for ms in (1, 15, 50, 120):
            cb.after(ms, _patch_combobox_dropdown_listbox, cb)

    cb.bind("<Button-1>", schedule_list_patch, add="+")
    cb.bind("<KeyPress-Down>", schedule_list_patch, add="+")


def _patch_combobox_dropdown_listbox(cb: ttk.Combobox) -> None:
    try:
        pop = str(cb.tk.call("ttk::combobox::PopdownWindow", cb._w))
    except tk.TclError:
        return
    try:
        kids = cb.tk.split(cb.tk.call("winfo", "children", pop))
    except tk.TclError:
        return
    for kid in kids:
        try:
            if str(cb.tk.call("winfo", "class", kid)) != "Listbox":
                continue
            cb.tk.call(kid, "configure", "-justify", "right")
        except tk.TclError:
            continue
