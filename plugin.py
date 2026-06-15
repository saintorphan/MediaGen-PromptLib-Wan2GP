"""MediaGen Prompt Library — a Wan2GP plugin.

A standalone, model-agnostic prompt library injected straight into the **Media
Generation** tab, just above the Lora Profile (lset) shortcuts at the top. Save
the current prompt + negative — optionally every generation parameter too —
tagged with the model selected at save time, then **Populate Fields** to load any
saved entry back onto whatever model is currently selected.

Prompts are NOT model-specific: the model tag only records what an entry was
*made for*; you can populate it onto any model. Reference media isn't stored.

Mechanism: the panel reads / writes the live per-model settings dict via the
host's ``get_current_model_settings`` and forces a form refresh by pinging the
``refresh_form_trigger`` (the same plumbing the bundled sample plugin uses).

NOTE: not an official plugin. Distribute via the plugin-manager "add from GitHub
URL" flow.
"""
from __future__ import annotations

import time
import traceback

import gradio as gr

from shared.utils.plugins import WAN2GPPlugin

from .core import store

PLUGIN_ID = "MediaGenPromptLib"
PLUGIN_NAME = "Prompt Library"

# Injection anchor: the (hidden) image-modal Column that sits immediately ABOVE
# the Lora Profile (lset) shortcuts Row in the Media Generation tab — they are
# siblings in the same parent column, so insert_after drops our panel between
# them, i.e. above the shortcuts (see wgp.py generate_media_tab).
_ANCHOR = "image-modal-container"

_HELP = (
    "Save the current **prompt** + **negative** — optionally **all** generation "
    "parameters — as a reusable entry, tagged with the model you have selected. "
    "Prompts aren't model-specific: **Populate Fields** loads one onto whatever "
    "model is currently selected. Reference media isn't stored."
)


class MediaGenPromptLibrary(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name = PLUGIN_NAME
        self.version = "0.1.0"
        self.description = (
            "Standalone, model-agnostic prompt library in the Media Generation "
            "tab: save / update / populate / delete prompts, optionally preserving "
            "all parameters, each tagged with the model used."
        )

    # -- lifecycle ----------------------------------------------------------
    def setup_ui(self):
        # Live-form plumbing (the handles the bundled sample plugin uses).
        self.request_component("state")
        self.request_component("refresh_form_trigger")
        self.request_global("get_current_model_settings")
        self.request_global("get_state_model_type")
        self.request_global("get_model_name")
        # Drop our panel above the Lora Profile shortcuts.
        self.insert_after(_ANCHOR, self._build_panel)

    # -- helpers ------------------------------------------------------------
    def _current(self, state):
        """(settings_dict, model_type, model_name) for the active model. The
        settings dict is the live per-model dict — mutating it in place and then
        pinging refresh_form_trigger rebuilds the form from it."""
        settings = self.get_current_model_settings(state)
        try:
            model_type = self.get_state_model_type(state)
        except Exception:
            model_type = settings.get("model_type", "") if isinstance(settings, dict) else ""
        try:
            model_name = self.get_model_name(model_type)
        except Exception:
            model_name = model_type or ""
        return settings, model_type, model_name

    @staticmethod
    def _msg(text):
        return gr.update(value=text)

    @staticmethod
    def _tag(entry):
        if not entry:
            return ""
        name = entry.get("model_name") or entry.get("model_type") or "?"
        extra = " · all parameters" if entry.get("preserve") else ""
        return f"🏷 Saved for **{name}**{extra}."

    # -- panel (the insert_after constructor; called no-arg) ------------------
    def _build_panel(self):
        state = self.state
        trigger = self.refresh_form_trigger

        def _save(state, name, preserve):
            name = (name or "").strip()
            if not name:
                return gr.update(), self._msg("Enter a name first.")
            try:
                settings, mtype, mname = self._current(state)
                entry = store.make_entry(
                    settings.get("prompt", ""), settings.get("negative_prompt", ""),
                    mtype, mname, settings if preserve else None,
                )
                choices = store.save(name, entry)
                return gr.update(choices=choices, value=name), self._msg(f"Saved “{name}”. {self._tag(entry)}")
            except Exception:
                traceback.print_exc()
                return gr.update(), self._msg("Save failed — see console.")

        def _update(state, sel, preserve):
            if not sel:
                return gr.update(), self._msg("Pick a saved entry to update.")
            try:
                settings, mtype, mname = self._current(state)
                entry = store.make_entry(
                    settings.get("prompt", ""), settings.get("negative_prompt", ""),
                    mtype, mname, settings if preserve else None,
                )
                choices = store.save(sel, entry)
                return gr.update(choices=choices, value=sel), self._msg(f"Updated “{sel}”. {self._tag(entry)}")
            except Exception:
                traceback.print_exc()
                return gr.update(), self._msg("Update failed — see console.")

        def _delete(sel):
            if not sel:
                return gr.update(), self._msg("Pick a saved entry to delete.")
            choices = store.delete(sel)
            return gr.update(choices=choices, value=None), self._msg(f"Deleted “{sel}”.")

        def _populate(state, sel):
            if not sel:
                return gr.update(), self._msg("Pick a saved entry to populate.")
            entry = store.get(sel)
            if not entry:
                return gr.update(), self._msg("That entry no longer exists.")
            try:
                settings = self.get_current_model_settings(state)
                settings["prompt"] = entry.get("prompt", "")
                settings["negative_prompt"] = entry.get("negative_prompt", "")
                applied = ""
                params = entry.get("params")
                if isinstance(params, dict):
                    for k, v in params.items():
                        settings[k] = v
                    applied = f" + {len(params)} parameter(s)"
                # New timestamp -> refresh_form_trigger.change -> fill_inputs rebuilds the form.
                return time.time(), self._msg(f"Populated prompts{applied} from “{sel}”. {self._tag(entry)}")
            except Exception:
                traceback.print_exc()
                return gr.update(), self._msg("Populate failed — see console.")

        def _on_select(sel):
            return self._msg(self._tag(store.get(sel)) if sel else "")

        with gr.Accordion(f"📚 {PLUGIN_NAME}", open=False) as panel:
            gr.Markdown(_HELP)
            with gr.Row():
                pl_name = gr.Textbox(label="Name", placeholder="e.g. moody portrait", scale=2)
                pl_saved = gr.Dropdown(label="Saved prompts", choices=store.names(), value=None, scale=2)
            pl_preserve = gr.Checkbox(
                label="Preserve all parameters", value=False,
                info="Also snapshot every generation setting (steps, guidance, "
                     "resolution, seed, LoRAs…). Off = prompt + negative only.",
            )
            with gr.Row():
                pl_save = gr.Button("💾 Save Current Prompts", size="sm")
                pl_update = gr.Button("⟳ Update", size="sm")
                pl_populate = gr.Button("📥 Populate Fields", variant="primary", size="sm")
                pl_delete = gr.Button("🗑 Delete", variant="stop", size="sm")
            pl_status = gr.Markdown("")

            pl_save.click(_save, inputs=[state, pl_name, pl_preserve], outputs=[pl_saved, pl_status])
            pl_update.click(_update, inputs=[state, pl_saved, pl_preserve], outputs=[pl_saved, pl_status])
            pl_delete.click(_delete, inputs=[pl_saved], outputs=[pl_saved, pl_status])
            pl_populate.click(_populate, inputs=[state, pl_saved], outputs=[trigger, pl_status])
            pl_saved.change(_on_select, inputs=[pl_saved], outputs=[pl_status])

        return panel


Plugin = MediaGenPromptLibrary
