"""
Interface graphique — Game Fence : blocage d'applications par plage horaire (Windows).
"""
from __future__ import annotations

import threading
import time as time_mod
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

import uuid

import clock_sync

try:
    import keyboard
except ImportError:
    keyboard = None  # type: ignore[assignment]

from core import (
    ACCESS_LOG_PATH,
    CLOCK_COMPARE_POLL_INTERVAL_SEC,
    CONFIG_PATH,
    AppConfig,
    BlockRule,
    KIND_AUTHORIZE_WINDOW,
    KIND_BLOCK_ALL,
    KIND_LEGACY_BLOCK_INSIDE,
    KIND_MARKER,
    append_access_log_entries,
    append_clock_compare_log_entries,
    default_rule_schedule,
    end_is_end_of_calendar_day,
    enforce_rules,
    is_rule_blocking_now,
    load_access_log_entries,
    load_clock_compare_log_entries,
    load_config,
    clock_compare_run,
    normalize_schedule,
    parse_clock,
    reference_wall_clock_naive,
    save_config,
    scan_rule_exe_access_events,
    pc_clock_tamper_banner_red_this_week,
)
from i18n import (
    attach_rtl_combobox_alignment,
    ensure_compact_treeview_style,
    hotkey_display,
    hotkey_keyword,
    install_locale,
    is_rtl,
    mode_labels_tuple,
    mono_font_tuple,
    normalize_locale,
    schedule_summary,
    rtl_text_embed,
    tk_align_text,
    tk_justify_paragraph,
    tr,
    ui_font_tuple,
    weekday_full,
)


class RuleEditor(tk.Toplevel):
    """Éditeur de règle : modes jour en combobox (voir mode_labels_tuple / JSON)."""

    def __init__(self, parent: tk.Tk, rule: Optional[BlockRule] = None) -> None:
        super().__init__(parent)
        self.title(tr("rule.title"))
        self._ui_font = ui_font_tuple(parent)
        self._mode_labels = mode_labels_tuple()
        rtl = is_rtl()
        self.resizable(True, True)
        self.minsize(720, 640)
        self.result: Optional[BlockRule] = None

        self._existing_id: Optional[str] = rule.id if rule else None
        r = rule
        self._name = tk.StringVar(value=r.display_name if r else "")
        self._exe = tk.StringVar(value=r.exe_name if r else "")
        self._enabled = tk.BooleanVar(value=r.enabled if r else True)

        base = normalize_schedule(rule.schedule) if rule else default_rule_schedule()
        self._start_v: dict[int, tk.StringVar] = {}
        self._end_v: dict[int, tk.StringVar] = {}
        self._ent_start: dict[int, ttk.Entry] = {}
        self._ent_end: dict[int, ttk.Entry] = {}
        self._mode_combo: dict[int, ttk.Combobox] = {}

        pad = {"padx": 6, "pady": 4}
        outer = ttk.Frame(self, padding=(12, 12, 12, 8))
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Barre d’actions FIXE en bas (sinon hors écran avec le formulaire long) ---
        footer = ttk.Frame(outer)
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))
        btn_row = ttk.Frame(footer)
        btn_row.pack(fill=tk.X)
        if rtl:
            ttk.Button(btn_row, text=tr("rule.ok"), command=self._ok).pack(side=tk.LEFT)
            ttk.Button(btn_row, text=tr("rule.cancel"), command=self.destroy).pack(side=tk.LEFT, padx=6)
            ttk.Label(
                btn_row,
                text=tr("rule.ok_hint"),
                foreground="#555",
                font=self._ui_font,
            ).pack(side=tk.RIGHT, padx=12)
            ttk.Checkbutton(btn_row, text=tr("rule.enabled"), variable=self._enabled).pack(side=tk.RIGHT)
        else:
            ttk.Checkbutton(btn_row, text=tr("rule.enabled"), variable=self._enabled).pack(side=tk.LEFT)
            ttk.Label(
                btn_row,
                text=tr("rule.ok_hint"),
                foreground="#555",
                font=self._ui_font,
            ).pack(side=tk.LEFT, padx=12)
            ttk.Button(btn_row, text=tr("rule.cancel"), command=self.destroy).pack(side=tk.RIGHT, padx=6)
            ttk.Button(btn_row, text=tr("rule.ok"), command=self._ok).pack(side=tk.RIGHT)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(body)
        top.pack(fill=tk.X, **pad)
        if rtl:
            ttk.Entry(top, textvariable=self._name, width=52).pack(side=tk.RIGHT, fill=tk.X, expand=True)
            ttk.Label(top, text=tr("rule.display_name")).pack(side=tk.RIGHT, padx=(8, 0))
        else:
            ttk.Label(top, text=tr("rule.display_name")).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Entry(top, textvariable=self._name, width=52).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row_exe = ttk.Frame(body)
        row_exe.pack(fill=tk.X, **pad)
        if rtl:
            ttk.Button(row_exe, text=tr("rule.browse"), command=self._browse).pack(side=tk.RIGHT)
            ttk.Entry(row_exe, textvariable=self._exe, width=40).pack(
                side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0)
            )
            ttk.Label(row_exe, text=tr("rule.exe_file")).pack(side=tk.RIGHT, padx=(0, 8))
        else:
            ttk.Label(row_exe, text=tr("rule.exe_file")).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Entry(row_exe, textvariable=self._exe, width=40).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
            )
            ttk.Button(row_exe, text=tr("rule.browse"), command=self._browse).pack(side=tk.LEFT)

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        hint = tr("rule.hint")
        ttk.Label(body, text=hint, foreground="#333", justify=tk_justify_paragraph(), wraplength=680).pack(
            anchor=tk_align_text(), pady=(0, 8)
        )

        scroll_fr = ttk.Frame(body)
        scroll_fr.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(scroll_fr, highlightthickness=0)
        vsb = ttk.Scrollbar(scroll_fr, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        if rtl:
            canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.LEFT, fill=tk.Y)
        else:
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = ttk.Frame(canvas)
        # Toujours ancrer en NW : avec NE à (0,0) le cadre s'étend en x < 0 et disparaît (bug RTL).
        inner_window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def _on_inner_configure(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e: tk.Event) -> None:
            canvas.itemconfigure(inner_window, width=max(1, e.width))

        def _wheel(e: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind("<Enter>", lambda _e: canvas.focus_set())
        canvas.bind("<MouseWheel>", _wheel)

        plan_lb = ttk.LabelFrame(inner, text=tr("rule.plan_frame"))
        plan_lb.pack(fill=tk.BOTH, expand=True, padx=0)

        for d in range(7):
            sl = base[d]
            self._start_v[d] = tk.StringVar(value=(sl or {}).get("start", "") or "")
            self._end_v[d] = tk.StringVar(value=(sl or {}).get("end", "") or "")

            block = ttk.Frame(plan_lb)
            block.pack(fill=tk.X, pady=(8, 2))

            wd_font = (self._ui_font[0], 10, "bold")
            ttk.Label(block, text=weekday_full(d), font=wd_font).pack(anchor=tk.E if rtl else tk.W)

            row_cb = ttk.Frame(block)
            row_cb.pack(fill=tk.X, pady=(2, 0))
            cb = ttk.Combobox(
                row_cb,
                values=self._mode_labels,
                state="readonly",
                width=72,
                font=self._ui_font,
            )
            cb.current(RuleEditor._slot_to_combo_index(sl))
            cb.pack(side=tk.RIGHT if rtl else tk.LEFT, fill=tk.X, expand=False)
            attach_rtl_combobox_alignment(cb)
            self._mode_combo[d] = cb

            row_e = ttk.Frame(block)
            row_e.pack(fill=tk.X, pady=(2, 0), padx=(4, 0))
            es = ttk.Entry(row_e, textvariable=self._start_v[d], width=9)
            ee = ttk.Entry(row_e, textvariable=self._end_v[d], width=9)
            if rtl:
                ee.pack(side=tk.RIGHT)
                ttk.Label(row_e, text="→").pack(side=tk.RIGHT, padx=4)
                es.pack(side=tk.RIGHT)
                ttk.Label(row_e, text=tr("rule.hours")).pack(side=tk.RIGHT, padx=(0, 8))
            else:
                ttk.Label(row_e, text=tr("rule.hours")).pack(side=tk.LEFT, padx=(0, 8))
                es.pack(side=tk.LEFT)
                ttk.Label(row_e, text="→").pack(side=tk.LEFT, padx=4)
                ee.pack(side=tk.LEFT)
            self._ent_start[d] = es
            self._ent_end[d] = ee

            cb.bind("<<ComboboxSelected>>", lambda _e, dd=d: self._sync_row(dd))
            self._sync_row(d)

        foot = tr("rule.legend")
        ttk.Label(
            inner,
            text=foot,
            foreground="#444",
            font=self._ui_font,
            justify=tk_justify_paragraph(),
            wraplength=680,
        ).pack(fill=tk.X, anchor=tk_align_text(), pady=(8, 4))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        self._wait_focus()

    @staticmethod
    def _slot_to_combo_index(slot: Optional[dict]) -> int:
        if slot is None:
            return 2
        k = slot.get(KIND_MARKER)
        if k == KIND_BLOCK_ALL:
            return 0
        if k == KIND_LEGACY_BLOCK_INSIDE:
            return 3
        if k == KIND_AUTHORIZE_WINDOW:
            return 1
        return 1

    def _sync_row(self, d: int) -> None:
        ix = self._mode_combo[d].current()
        if ix < 0:
            ix = 2
        st = tk.DISABLED if ix in (0, 2) else tk.NORMAL
        try:
            self._ent_start[d].configure(state=st)
            self._ent_end[d].configure(state=st)
        except tk.TclError:
            pass

    def _wait_focus(self) -> None:
        self.update_idletasks()
        w, h = 700, 520
        try:
            x = self.master.winfo_rootx() + 28
            y = self.master.winfo_rooty() + 20
            self.geometry(f"{w}x{h}+{x}+{y}")
        except tk.TclError:
            self.geometry(f"{w}x{h}")

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("rule.browse_title"),
            filetypes=[(tr("rule.file_exe"), "*.exe"), (tr("rule.file_all"), "*.*")],
        )
        if path:
            from pathlib import Path

            self._exe.set(Path(path).name)

    def _ok(self) -> None:
        name = self._name.get().strip()
        exe = self._exe.get().strip()
        if not exe:
            messagebox.showwarning(tr("msg.validation_title"), tr("msg.rule_exe_missing"), parent=self)
            return
        if not exe.lower().endswith(".exe"):
            if not messagebox.askyesno(
                tr("msg.rule_extension_title"),
                tr("msg.rule_extension_body"),
                parent=self,
            ):
                return

        schedule: list[Optional[dict[str, Any]]] = []

        for d in range(7):
            cb = self._mode_combo[d]
            ix = cb.current()
            if ix < 0:
                ix = 2

            if ix == 2:
                schedule.append(None)
                continue
            if ix == 0:
                schedule.append({KIND_MARKER: KIND_BLOCK_ALL})
                continue

            sta = self._start_v[d].get().strip()
            en = self._end_v[d].get().strip()
            kind = KIND_AUTHORIZE_WINDOW if ix == 1 else KIND_LEGACY_BLOCK_INSIDE

            if not sta or not en:
                messagebox.showwarning(
                    tr("msg.validation_title"),
                    tr("msg.rule_interval_missing", weekday=weekday_full(d)),
                    parent=self,
                )
                return
            try:
                parse_clock(sta)
            except (ValueError, IndexError):
                messagebox.showwarning(
                    tr("msg.validation_title"),
                    tr("msg.rule_start_invalid", weekday=weekday_full(d)),
                    parent=self,
                )
                return

            if end_is_end_of_calendar_day(en):
                schedule.append({KIND_MARKER: kind, "start": sta, "end": en})
                continue

            try:
                t1 = parse_clock(sta)
                t2 = parse_clock(en)
            except (ValueError, IndexError):
                messagebox.showwarning(
                    tr("msg.validation_title"),
                    tr("msg.rule_times_invalid", weekday=weekday_full(d)),
                    parent=self,
                )
                return
            if t1 >= t2:
                messagebox.showwarning(
                    tr("msg.validation_title"),
                    tr("msg.rule_order_invalid", weekday=weekday_full(d)),
                    parent=self,
                )
                return
            schedule.append({KIND_MARKER: kind, "start": sta, "end": en})

        if all(s is None for s in schedule):
            messagebox.showwarning(
                tr("msg.validation_title"),
                tr("msg.rule_all_none"),
                parent=self,
            )
            return

        rid = self._existing_id or uuid.uuid4().hex[:12]
        self.result = BlockRule(
            id=rid,
            display_name=name or exe,
            exe_name=exe,
            enabled=self._enabled.get(),
            schedule=normalize_schedule(schedule),
        )
        self.destroy()


def _access_event_label(kind: str) -> str:
    key = f"access_log.kind_{kind}"
    text = tr(key)
    return text if text != key else kind


class AccessLogWindow(tk.Toplevel):
    """Liste des ouvertures / tentatives pour les exécutables suivis par les règles."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title(tr("access_log.title"))
        self._ui_font = ui_font_tuple(parent)
        rtl = is_rtl()
        self.minsize(720, 420)
        self.geometry("820x480")

        outer = ttk.Frame(self, padding=(12, 12, 12, 8))
        outer.pack(fill=tk.BOTH, expand=True)

        hint = ttk.Label(
            outer,
            text=tr("access_log.hint", path=str(ACCESS_LOG_PATH)),
            foreground="#555",
            font=self._ui_font,
            wraplength=780,
            justify=tk_justify_paragraph(),
        )
        hint.pack(fill=tk.X, anchor=tk_align_text(), pady=(0, 8))

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        if rtl:
            ttk.Button(btn_row, text=tr("access_log.refresh"), command=self._reload).pack(side=tk.RIGHT)
        else:
            ttk.Button(btn_row, text=tr("access_log.refresh"), command=self._reload).pack(side=tk.LEFT)

        mid = ttk.Frame(outer)
        mid.pack(fill=tk.BOTH, expand=True)

        col_defs: list[tuple[str, str, int]] = [
            ("ts", tr("access_log.col_time"), 155),
            ("exe", tr("access_log.col_exe"), 130),
            ("name", tr("access_log.col_name"), 140),
            ("event", tr("access_log.col_event"), 260),
        ]
        if rtl:
            col_defs = list(reversed(col_defs))
        cols = tuple(d[0] for d in col_defs)
        self._tree_cols: tuple[str, ...] = cols

        self._tree = ttk.Treeview(
            mid,
            columns=cols,
            show="headings",
            selectmode="browse",
            style=ensure_compact_treeview_style(parent),
        )
        col_anchor = tk.E if rtl else tk.W
        for cid, header, w in col_defs:
            self._tree.heading(cid, text=header)
            self._tree.column(cid, width=w, anchor=col_anchor)

        sb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        if rtl:
            sb.pack(side=tk.LEFT, fill=tk.Y)
            self._tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        else:
            self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._reload()
        try:
            x = parent.winfo_rootx() + 40
            y = parent.winfo_rooty() + 28
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _reload(self) -> None:
        for i in self._tree.get_children():
            self._tree.delete(i)
        rows = load_access_log_entries()
        order = self._tree_cols
        if not rows:
            row_empty = {"ts": tr("access_log.empty"), "exe": "", "name": "", "event": ""}
            self._tree.insert("", tk.END, values=tuple(row_empty[c] for c in order))
            return
        for e in reversed(rows):
            ts = str(e.get("ts", "") or "")
            exe = str(e.get("exe", "") or "")
            dn = str(e.get("display_name", "") or "")
            kind = str(e.get("kind", "") or "")
            ev = _access_event_label(kind)
            row_map = {"ts": ts, "exe": exe, "name": dn, "event": ev}
            vals = tuple(row_map[c] for c in order)
            self._tree.insert("", tk.END, values=vals)


class ClockCompareWindow(tk.Toplevel):
    """Journal horloge : statut changement d’heure Windows (semaine civile) et tableau des mesures."""

    def __init__(self, app: tk.Tk) -> None:
        super().__init__(app)
        self._app = app
        self.title(tr("clock_compare.title"))
        self._ui_font = ui_font_tuple(app)
        rtl = is_rtl()
        self.minsize(780, 460)
        self.geometry("900x520")

        cfg: AppConfig = app._cfg  # type: ignore[attr-defined]

        outer = ttk.Frame(self, padding=(12, 12, 12, 8))
        outer.pack(fill=tk.BOTH, expand=True)

        settings = ttk.LabelFrame(outer, text=tr("clock_compare.settings_frame"), padding=8)
        settings.pack(fill=tk.X, pady=(0, 8))

        self._enabled_var = tk.BooleanVar(value=cfg.clock_compare_enabled)
        row1 = ttk.Frame(settings)
        row1.pack(fill=tk.X)
        self._compare_tz_combo = ttk.Combobox(
            row1,
            values=clock_sync.timezone_choice_labels(),
            state="readonly",
            width=10,
            font=self._ui_font,
        )
        tz_h = max(-12, min(14, int(cfg.clock_compare_offset_hours)))
        self._compare_tz_combo.current(tz_h + 12)
        if is_rtl():
            attach_rtl_combobox_alignment(self._compare_tz_combo)
        self._compare_tz_combo.bind("<<ComboboxSelected>>", self._persist_compare_timezone)

        cb_enable = ttk.Checkbutton(
            row1,
            text=tr("clock_compare.enable"),
            variable=self._enabled_var,
            command=self._persist_enabled,
        )
        lbl_zone = ttk.Label(row1, text=tr("clock_compare.zone_label"), font=self._ui_font)
        self._ref_tz_clock_lbl = ttk.Label(
            row1,
            text="",
            font=self._ui_font,
            foreground="#222",
        )

        self._ref_clock_after_id: Optional[int] = None

        if rtl:
            cb_enable.pack(side=tk.RIGHT)
            lbl_zone.pack(side=tk.RIGHT, padx=8)
            self._compare_tz_combo.pack(side=tk.RIGHT)
            self._ref_tz_clock_lbl.pack(side=tk.RIGHT, padx=(12, 0))
        else:
            cb_enable.pack(side=tk.LEFT)
            lbl_zone.pack(side=tk.LEFT, padx=(16, 8))
            self._compare_tz_combo.pack(side=tk.LEFT)
            self._ref_tz_clock_lbl.pack(side=tk.LEFT, padx=(12, 0))

        desc_parts = [tr("clock_compare.settings_help")]
        h2 = tr("clock_compare.settings_help_2").strip()
        if h2:
            desc_parts.append(h2)
        desc_text = "\n".join(desc_parts)
        if rtl:
            desc_text = rtl_text_embed(desc_text)
        desc_surveillance = ttk.Label(
            settings,
            text=desc_text,
            font=self._ui_font,
            foreground="#444",
            wraplength=820,
            justify=tk_justify_paragraph(),
            anchor=tk_align_text(),
        )
        desc_surveillance.pack(fill=tk.X, anchor=tk_align_text(), pady=(10, 0))

        self.update_idletasks()
        try:
            lbl_bg = self.cget("background")
        except tk.TclError:
            lbl_bg = "#f0f0f0"
        bf = tkfont.Font(app, family=self._ui_font[0], size=max(int(self._ui_font[1]), 10), weight="bold")
        self._tamper_lbl = tk.Label(
            outer,
            text=rtl_text_embed(tr("clock_compare.tamper_loading")),
            font=bf,
            wraplength=820,
            justify=tk_justify_paragraph(),
            anchor=tk_align_text(),
            padx=8,
            pady=18,
            bg=lbl_bg,
        )
        self._tamper_lbl.pack(fill=tk.X, anchor=tk.CENTER)

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        if rtl:
            ttk.Button(btn_row, text=tr("clock_compare.refresh"), command=self._reload).pack(side=tk.RIGHT)
        else:
            ttk.Button(btn_row, text=tr("clock_compare.refresh"), command=self._reload).pack(side=tk.LEFT)

        mid = ttk.Frame(outer)
        mid.pack(fill=tk.BOTH, expand=True)

        col_defs: list[tuple[str, str, int]] = [
            ("checked_at", tr("clock_compare.col_checked_at"), 168),
            ("skew", tr("clock_compare.col_skew"), 72),
            ("zone", tr("clock_compare.col_zone"), 72),
            ("reference_wall", tr("clock_compare.col_reference"), 158),
            ("system_local_wall", tr("clock_compare.col_system_local"), 158),
        ]
        if rtl:
            col_defs = list(reversed(col_defs))
        cols = tuple(d[0] for d in col_defs)
        self._tree_cols: tuple[str, ...] = cols

        self._tree = ttk.Treeview(
            mid,
            columns=cols,
            show="headings",
            selectmode="browse",
            style=ensure_compact_treeview_style(app),
        )
        col_anchor = tk.E if rtl else tk.W
        for cid, header, w in col_defs:
            self._tree.heading(cid, text=header)
            self._tree.column(cid, width=w, anchor=col_anchor)

        sb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        if rtl:
            sb.pack(side=tk.LEFT, fill=tk.Y)
            self._tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        else:
            self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self._on_close_clock_compare)
        self._schedule_ref_clock_tick()
        self._reload()
        try:
            x = app.winfo_rootx() + 48
            y = app.winfo_rooty() + 36
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _on_close_clock_compare(self) -> None:
        aid = getattr(self, "_ref_clock_after_id", None)
        if aid is not None:
            try:
                self.after_cancel(aid)
            except tk.TclError:
                pass
            self._ref_clock_after_id = None
        self.destroy()

    def _update_ref_clock_display(self) -> None:
        seq = list(range(-12, 15))
        try:
            i = self._compare_tz_combo.current()
            off = seq[i] if 0 <= i < len(seq) else self._app._cfg.clock_compare_offset_hours  # type: ignore[attr-defined]
        except (tk.TclError, TypeError, ValueError):
            return
        off = max(-12, min(14, int(off)))
        try:
            utc = clock_sync.effective_utc_now()
            wall = clock_sync.wall_clock_naive_for_offset_hours(utc, off).replace(microsecond=0)
            txt = wall.strftime("%Y-%m-%d %H:%M:%S")
            src = tr("watch.src_ntp") if clock_sync.clock_source_was_ntp() else tr("watch.src_system")
            self._ref_tz_clock_lbl.configure(text=tr("watch.ref_time", dt=txt, src=src))
        except tk.TclError:
            pass

    def _schedule_ref_clock_tick(self) -> None:
        prev = getattr(self, "_ref_clock_after_id", None)
        if prev is not None:
            try:
                self.after_cancel(prev)
            except tk.TclError:
                pass
            self._ref_clock_after_id = None

        def tick() -> None:
            self._ref_clock_after_id = None
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return
            self._update_ref_clock_display()
            try:
                self._ref_clock_after_id = self.after(1000, tick)
            except tk.TclError:
                pass

        self._update_ref_clock_display()
        try:
            self._ref_clock_after_id = self.after(1000, tick)
        except tk.TclError:
            pass

    def _persist_enabled(self) -> None:
        cfg: AppConfig = self._app._cfg  # type: ignore[attr-defined]
        cfg.clock_compare_enabled = bool(self._enabled_var.get())
        save_config(cfg)
        self._reload()

    def _persist_compare_timezone(self, _event: tk.Event | None = None) -> None:
        seq = list(range(-12, 15))
        i = self._compare_tz_combo.current()
        if i < 0 or i >= len(seq):
            return
        cfg: AppConfig = self._app._cfg  # type: ignore[attr-defined]
        h = seq[i]
        if h != cfg.clock_compare_offset_hours:
            cfg.clock_compare_offset_hours = h
            save_config(cfg)
        self._update_tamper_banner_async()
        self._update_ref_clock_display()

    def _reload(self) -> None:
        cfg: AppConfig = self._app._cfg  # type: ignore[attr-defined]
        _, entry = clock_compare_run(cfg, emit_log_entry=True)
        if entry:
            append_clock_compare_log_entries([entry])
        self._fill_tree()
        self._update_tamper_banner_async()

    def _update_tamper_banner_async(self) -> None:
        win = self

        def work() -> None:
            try:
                changed = pc_clock_tamper_banner_red_this_week()
            except Exception:
                changed = False

            def apply_ui() -> None:
                try:
                    if not win.winfo_exists():
                        return
                except tk.TclError:
                    return
                if changed:
                    win._tamper_lbl.configure(
                        text=rtl_text_embed(tr("clock_compare.tamper_yes")),
                        fg="#b00000",
                    )
                else:
                    win._tamper_lbl.configure(
                        text=rtl_text_embed(tr("clock_compare.tamper_no")),
                        fg="#0d8228",
                    )

            try:
                win.after(0, apply_ui)
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _fill_tree(self) -> None:
        for i in self._tree.get_children():
            self._tree.delete(i)
        rows = load_clock_compare_log_entries()
        order = self._tree_cols
        if not rows:
            empty_row = {c: "" for c in order}
            empty_row["checked_at"] = tr("clock_compare.empty")
            self._tree.insert("", tk.END, values=tuple(empty_row[c] for c in order))
            return
        tz_labels = clock_sync.timezone_choice_labels()
        for e in reversed(rows):
            checked_at = str(e.get("checked_at", "") or "")
            try:
                skew_n = int(e.get("skew_seconds", 0))
            except (TypeError, ValueError):
                skew_n = 0
            skew_disp = str(skew_n)
            try:
                zh = int(e.get("compare_utc_hours", 0))
            except (TypeError, ValueError):
                zh = 0
            zh = max(-12, min(14, zh))
            zone_txt = tz_labels[zh + 12]
            ref_w = str(e.get("reference_wall", "") or "")
            sys_w = str(e.get("system_local_wall", "") or "")
            row_map = {
                "checked_at": checked_at,
                "skew": skew_disp,
                "zone": zone_txt,
                "reference_wall": ref_w,
                "system_local_wall": sys_w,
            }
            self._tree.insert("", tk.END, values=tuple(row_map[c] for c in order))


class GameFenceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.withdraw()

        self._cfg: AppConfig = load_config()
        install_locale(normalize_locale(self._cfg.ui_locale), self)
        self.title(tr("app.title"))
        self.minsize(860, 540)
        self.geometry("960x640")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._log_lock = threading.Lock()
        self._access_prev_running: dict[str, bool] = {}
        self._hotkey_unregister: Optional[Callable[[], None]] = None
        self._clock_tick_id: Optional[int] = None
        self._clock_compare_after_id: Optional[int] = None

        self._build_ui()
        self._refresh_tree()
        self._start_worker()
        self._register_global_hotkey()
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self._ntp_initial_sync_bg()

    def _set_locale(self, code: str) -> None:
        code = normalize_locale(code)
        if code == getattr(self._cfg, "ui_locale", None):
            return
        self._cfg.ui_locale = code
        save_config(self._cfg)
        install_locale(code, self)
        self.title(tr("app.title"))
        state = self.wm_state()
        self._unregister_global_hotkey()
        for child in list(self.winfo_children()):
            child.destroy()
        self._build_ui()
        self._refresh_tree()
        self._register_global_hotkey()
        if state == "withdrawn":
            self.withdraw()

    def destroy(self) -> None:
        self._unregister_global_hotkey()
        cid = getattr(self, "_clock_compare_after_id", None)
        if cid is not None:
            try:
                self.after_cancel(cid)
            except tk.TclError:
                pass
            self._clock_compare_after_id = None
        super().destroy()

    def _build_ui(self) -> None:
        rtl = is_rtl()
        tick_prev = getattr(self, "_clock_tick_id", None)
        if tick_prev is not None:
            try:
                self.after_cancel(tick_prev)
            except tk.TclError:
                pass
            self._clock_tick_id = None

        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=tr("menu.access_log"), command=self._open_access_log)
        file_menu.add_command(label=tr("menu.clock_compare_log"), command=self._open_clock_compare_log)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu.quit"), command=self._quit_application)
        menubar.add_cascade(label=tr("menu.file"), menu=file_menu)
        lang_menu = tk.Menu(menubar, tearoff=0)
        for loc_code, label in (("fr", "Français"), ("en", "English"), ("ar", "العربية")):
            lang_menu.add_command(label=label, command=lambda c=loc_code: self._set_locale(c))
        menubar.add_cascade(label=tr("menu.language"), menu=lang_menu)
        self.config(menu=menubar)

        hk = hotkey_display()
        intro = "\n".join((tr("intro.line1"), tr("intro.line21", hotkey=hk), tr("intro.line22", hotkey=hk), tr("intro.line3")))
        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.pack(fill=tk.X)

        ui_f = ui_font_tuple(self)
        j_intro = tk_justify_paragraph()
        ttk.Label(top, text=intro, wraplength=900, font=ui_f, justify=j_intro).pack(anchor=tk_align_text())

        ctl = ttk.Frame(self, padding=(12, 4))
        ctl.pack(fill=tk.X)
        self._watch_var = tk.BooleanVar(value=True)
        self._interval_var = tk.StringVar(value=str(self._cfg.global_check_interval_seconds))
        ps = tk.RIGHT if rtl else tk.LEFT
        ttk.Checkbutton(
            ctl, text=tr("watch.active"), variable=self._watch_var, command=self._toggle_watch
        ).pack(side=ps)
        ttk.Label(ctl, text=tr("watch.interval"), font=ui_f).pack(side=ps)
        ttk.Entry(ctl, textvariable=self._interval_var, width=6).pack(side=ps, padx=6)

        tz_labels = clock_sync.timezone_choice_labels()
        self._tz_offset_sequence = list(range(-12, 15))
        ttk.Label(ctl, text=tr("watch.time_zone"), font=ui_f).pack(side=ps)
        self._tz_combo = ttk.Combobox(
            ctl,
            values=tz_labels,
            state="readonly",
            width=9,
            font=ui_f,
        )
        tz_h = max(-12, min(14, int(self._cfg.time_zone_offset_hours)))
        self._tz_combo.current(tz_h + 12)
        self._tz_combo.pack(side=ps, padx=(0, 8))
        if rtl:
            attach_rtl_combobox_alignment(self._tz_combo)
        self._tz_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_timezone_changed())

        self._clock_lbl = ttk.Label(ctl, text="", font=ui_f, foreground="#222")
        self._clock_lbl.pack(side=ps, padx=(0, 12))

        # ttk.Label(ctl, text=tr("watch.config", path=CONFIG_PATH), foreground="#555", font=ui_f).pack(
        #     side=tk.LEFT if rtl else tk.RIGHT
        # )

        # Barre de boutons + journal d’abord en bas pour qu’ils restent visibles même si le tableau est très haut.
        btn = ttk.Frame(self, padding=12)

        log_fr = ttk.LabelFrame(self, text=tr("log.recent"), padding=8)
        self._log = tk.Text(
            log_fr,
            height=4,
            state=tk.DISABLED,
            font=mono_font_tuple(self),
            wrap=tk.WORD,
        )
        self._log.pack(fill=tk.X)

        log_fr.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 10))
        btn.pack(side=tk.BOTTOM, fill=tk.X)

        mid = ttk.Frame(self, padding=(12, 4))
        mid.pack(fill=tk.BOTH, expand=True)

        # Ordre des colonnes : en RTL on inverse pour que la 1ʳᵉ colonne lue soit à droite.
        col_defs: list[tuple[str, str, int]] = [
            ("active", tr("tree.col_active"), 45),
            ("name", tr("tree.col_name"), 120),
            ("exe", tr("tree.col_exe"), 150),
            ("plan", tr("tree.col_plan"), 400),
            ("now", tr("tree.col_blocked"), 70),
        ]
        if rtl:
            col_defs = list(reversed(col_defs))
        cols = tuple(d[0] for d in col_defs)
        self._tree_value_keys: tuple[str, ...] = cols

        self._tree = ttk.Treeview(mid, columns=cols, show="headings", height=2, selectmode="browse")
        col_anchor = tk.E if rtl else tk.W
        for cid, header, w in col_defs:
            self._tree.heading(cid, text=header)
            self._tree.column(cid, width=w, anchor=col_anchor)

        sb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        if rtl:
            sb.pack(side=tk.LEFT, fill=tk.Y)
            self._tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        else:
            self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<Double-1>", lambda e: self._edit_rule())

        bp = tk.RIGHT if rtl else tk.LEFT
        if rtl:
            ttk.Button(btn, text=tr("btn.add_rule"), command=self._add_rule).pack(side=bp, padx=2)
            ttk.Button(btn, text=tr("btn.edit"), command=self._edit_rule).pack(side=bp, padx=2)
            ttk.Button(btn, text=tr("btn.delete"), command=self._delete_rule).pack(side=bp, padx=2)
            ttk.Button(btn, text=tr("btn.save"), command=self._save).pack(side=bp, padx=(16, 2))
        else:
            ttk.Button(btn, text=tr("btn.add_rule"), command=self._add_rule).pack(side=bp, padx=2)
            ttk.Button(btn, text=tr("btn.edit"), command=self._edit_rule).pack(side=bp, padx=2)
            ttk.Button(btn, text=tr("btn.delete"), command=self._delete_rule).pack(side=bp, padx=2)
            ttk.Button(btn, text=tr("btn.save"), command=self._save).pack(side=bp, padx=(16, 2))

        self._tick_clock_schedule()
        self._schedule_clock_compare_loop()

    def _schedule_clock_compare_loop(self) -> None:
        cmp_prev = getattr(self, "_clock_compare_after_id", None)
        if cmp_prev is not None:
            try:
                self.after_cancel(cmp_prev)
            except tk.TclError:
                pass
            self._clock_compare_after_id = None

        delay_ms = CLOCK_COMPARE_POLL_INTERVAL_SEC * 1000

        def tick() -> None:
            self._clock_compare_after_id = None
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return
            self._run_clock_compare_tick()
            try:
                self._clock_compare_after_id = self.after(delay_ms, tick)
            except tk.TclError:
                pass

        try:
            self._clock_compare_after_id = self.after(delay_ms, tick)
        except tk.TclError:
            pass

    def _run_clock_compare_tick(self) -> None:
        _, entry = clock_compare_run(self._cfg)
        if entry:
            append_clock_compare_log_entries([entry])

    def _tick_clock_display(self) -> None:
        try:
            if not self.winfo_exists():
                return
            ref = reference_wall_clock_naive(self._cfg)
            txt = ref.strftime("%Y-%m-%d %H:%M:%S")
            src = tr("watch.src_ntp") if clock_sync.clock_source_was_ntp() else tr("watch.src_system")
            self._clock_lbl.configure(text=tr("watch.ref_time", dt=txt, src=src))
        except (tk.TclError, AttributeError, ValueError, OSError):
            pass

    def _tick_clock_schedule(self) -> None:
        self._tick_clock_display()
        try:
            self._clock_tick_id = self.after(1000, self._tick_clock_schedule)
        except tk.TclError:
            self._clock_tick_id = None

    def _on_timezone_changed(self) -> None:
        seq = getattr(self, "_tz_offset_sequence", [])
        i = self._tz_combo.current()
        if i < 0 or i >= len(seq):
            return
        hours = seq[i]
        if hours != self._cfg.time_zone_offset_hours:
            self._cfg.time_zone_offset_hours = hours
            save_config(self._cfg)

        def run() -> None:
            clock_sync.sync_ntp()
            try:
                self.after(0, self._tick_clock_display)
                self.after(0, self._refresh_tree)
            except tk.TclError:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _ntp_initial_sync_bg(self) -> None:
        def run() -> None:
            clock_sync.sync_ntp()
            try:
                self.after(0, self._tick_clock_display)
            except tk.TclError:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _register_global_hotkey(self) -> None:
        self._unregister_global_hotkey()
        if keyboard is None:
            def _warn_no_keyboard() -> None:
                self.deiconify()
                messagebox.showwarning(
                    tr("msg.keyboard_title"),
                    tr("msg.keyboard_body", hotkey=hotkey_display()),
                    parent=self,
                )

            self.after(200, _warn_no_keyboard)
            return

        keyword = hotkey_keyword()

        def on_event(ev: Any) -> None:
            try:
                if ev.event_type != keyboard.KEY_DOWN:
                    return
            except AttributeError:
                return
            name = getattr(ev, "name", "") or ""
            if str(name).lower() != keyword:
                return
            try:
                if keyboard.is_pressed("ctrl") and keyboard.is_pressed("shift"):
                    self.after(0, self._show_window)
            except Exception:
                return

        try:
            self._hotkey_unregister = keyboard.hook(on_event, suppress=False)
        except Exception as e:  # noqa: BLE001 — surface d’installation / droits variés
            def _err_hotkey(err: BaseException = e) -> None:
                self.deiconify()
                messagebox.showerror(
                    tr("msg.hotkey_title"),
                    tr("msg.hotkey_body", hotkey=hotkey_display(), err=err),
                    parent=self,
                )

            self.after(250, _err_hotkey)

    def _unregister_global_hotkey(self) -> None:
        u = self._hotkey_unregister
        self._hotkey_unregister = None
        if u is not None:
            try:
                u()
            except Exception:
                pass

    def _show_window(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(80, lambda: self.attributes("-topmost", False))
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def _open_access_log(self) -> None:
        AccessLogWindow(self)

    def _open_clock_compare_log(self) -> None:
        ClockCompareWindow(self)

    def _quit_application(self) -> None:
        self._stop_worker()
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _append_log(self, line: str) -> None:
        line_out = rtl_text_embed(line.rstrip("\n")) + "\n"
        with self._log_lock:
            self._log.configure(state=tk.NORMAL)
            self._log.insert(tk.END, line_out)
            self._log.see(tk.END)
            while int(self._log.index("end-1c").split(".")[0]) > 80:
                self._log.delete("1.0", "2.0")
            self._log.configure(state=tk.DISABLED)

    def _refresh_tree(self) -> None:
        for i in self._tree.get_children():
            self._tree.delete(i)
        order = getattr(self, "_tree_value_keys", ("active", "name", "exe", "plan", "now"))
        for r in self._cfg.rules:
            blocking_now = is_rule_blocking_now(r, self._cfg)
            row_by_id = {
                "active": tr("yes") if r.enabled else tr("no"),
                "name": r.display_name,
                "exe": r.exe_name,
                "plan": schedule_summary(r),
                "now": tr("yes") if blocking_now else tr("no"),
            }
            values = tuple(row_by_id[k] for k in order)
            self._tree.insert(
                "",
                tk.END,
                iid=r.id,
                values=values,
            )

    def _selected_rule_id(self) -> Optional[str]:
        sel = self._tree.selection()
        return str(sel[0]) if sel else None

    def _add_rule(self) -> None:
        dlg = RuleEditor(self, None)
        self.wait_window(dlg)
        if dlg.result:
            self._cfg.rules.append(dlg.result)
            self._refresh_tree()

    def _edit_rule(self) -> None:
        rid = self._selected_rule_id()
        if not rid:
            messagebox.showinfo(tr("msg.selection_title"), tr("msg.selection_body"))
            return
        rule = next((r for r in self._cfg.rules if r.id == rid), None)
        if not rule:
            return
        dlg = RuleEditor(self, rule)
        self.wait_window(dlg)
        if dlg.result:
            for i, r in enumerate(self._cfg.rules):
                if r.id == rid:
                    self._cfg.rules[i] = dlg.result
                    break
            self._refresh_tree()

    def _delete_rule(self) -> None:
        rid = self._selected_rule_id()
        if not rid:
            return
        if not messagebox.askyesno(tr("msg.confirm_title"), tr("msg.confirm_delete")):
            return
        self._cfg.rules = [r for r in self._cfg.rules if r.id != rid]
        self._refresh_tree()

    def _save(self) -> None:
        try:
            iv = max(5, min(600, int(self._interval_var.get().strip())))
        except ValueError:
            messagebox.showerror(tr("msg.interval_error_title"), tr("msg.interval_error"))
            return
        self._cfg.global_check_interval_seconds = iv
        save_config(self._cfg)
        self.after(
            0,
            lambda: self._append_log(tr("log.saved")),
        )

    def _toggle_watch(self) -> None:
        if self._watch_var.get():
            self._start_worker()
        else:
            self._stop_worker()

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                iv = int(self._interval_var.get().strip())
            except ValueError:
                iv = self._cfg.global_check_interval_seconds
            iv = max(5, min(600, iv))
            if self._watch_var.get():
                clock_sync.maybe_resync_ntp()
                access_rows, self._access_prev_running = scan_rule_exe_access_events(
                    self._cfg, self._access_prev_running
                )
                if access_rows:
                    append_access_log_entries(access_rows)
                killed = enforce_rules(self._cfg)
                if killed:
                    for exe, title in killed:
                        msg = tr("log.process_killed", title=title, exe=exe)
                        self.after(0, lambda m=msg: self._append_log(m))
                self.after(0, self._refresh_tree)
            wait = iv
            for _ in range(wait * 10):
                if self._stop.is_set():
                    break
                time_mod.sleep(0.1)

    def _start_worker(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def _stop_worker(self) -> None:
        self._stop.set()

    def _on_close_request(self) -> None:
        if self.grab_current():
            messagebox.showwarning(
                tr("msg.dialog_open_title"),
                tr("msg.dialog_open_body"),
                parent=self,
            )
            return
        self.withdraw()


def main() -> None:
    app = GameFenceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
