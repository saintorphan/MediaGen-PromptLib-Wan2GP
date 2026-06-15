"""MediaGen Prompt Library — a Wan2GP plugin.

A standalone, model-agnostic prompt library added as a collapsible panel in the
**Media Generation** tab, directly below the **Generate** button. Save the
current prompt + negative — optionally every generation parameter too — tagged
with the model selected at save time, then **Populate Fields** to load any saved
entry back onto whatever model is currently selected.

Prompts are NOT model-specific: the model tag only records what an entry was
*made for*; you can populate it onto any model. Reference media isn't stored.

Mechanism: Save reads the live prompt / negative textboxes directly (requested as
components) so it captures what's typed, plus — when "preserve all parameters" is
on — the last-applied generation settings via ``get_current_model_settings``.
Populate writes the per-model settings dict and forces a form refresh by pinging
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

PLUGIN_NAME = "Prompt Library"

# Injection anchor. The host resolves insert_after targets against the LOCAL
# VARIABLE NAMES of generate_media_tab (it passes locals() as the component map —
# see wgp.py `app.run_component_insertion(locals())`), NOT against elem_id.
# `generate_btn` is the "Generate" gr.Button; its parent is the form's main
# vertical Column, so inserting a sibling there drops our panel directly below
# the Generate button — always visible, no Advanced Mode needed.
_ANCHOR = "generate_btn"

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
        self.version = "0.2.0"
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
        # The live prompt textboxes, so Save captures what the user has TYPED
        # rather than the last value committed to the settings dict (which only
        # syncs on Generate / Save Settings). These are local-var names in
        # generate_media_tab (wgp.py: `prompt`, `negative_prompt`); if a future
        # host renames them the panel falls back to the settings dict.
        self.request_component("prompt")
        self.request_component("negative_prompt")
        self.request_global("get_current_model_settings")
        self.request_global("get_state_model_type")
        self.request_global("get_model_name")
        # Drop our panel directly below the Generate button.
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
    def _live_prompt(settings, live):
        """Prefer the live prompt/negative textbox values (passed as click
        inputs); fall back to the committed settings dict if those components
        weren't available to request."""
        prompt = live[0] if len(live) >= 1 and live[0] is not None else settings.get("prompt", "")
        negative = live[1] if len(live) >= 2 and live[1] is not None else settings.get("negative_prompt", "")
        return prompt, negative

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
        # Live prompt/negative textboxes, if the host exposed them. Passed as
        # click inputs so Save reads what's typed now, not the committed dict.
        live_components = [c for c in (getattr(self, "prompt", None),
                                       getattr(self, "negative_prompt", None)) if c is not None]

        def _save(state, name, preserve, *live):
            name = (name or "").strip()
            if not name:
                return gr.update(), self._msg("Enter a name first.")
            try:
                settings, mtype, mname = self._current(state)
                prompt, negative = self._live_prompt(settings, live)
                existed = name in store.names()
                entry = store.make_entry(prompt, negative, mtype, mname, settings if preserve else None)
                choices = store.save(name, entry)
                if choices is None:
                    return gr.update(), self._msg("Save failed — could not write to disk (see console).")
                verb = "Overwrote" if existed else "Saved"
                return gr.update(choices=choices, value=name), self._msg(f"{verb} “{name}”.")
            except Exception:
                traceback.print_exc()
                return gr.update(), self._msg("Save failed — see console.")

        def _update(state, sel, preserve, *live):
            if not sel:
                return gr.update(), self._msg("Pick a saved entry to update.")
            try:
                settings, mtype, mname = self._current(state)
                prompt, negative = self._live_prompt(settings, live)
                entry = store.make_entry(prompt, negative, mtype, mname, settings if preserve else None)
                choices = store.save(sel, entry)
                if choices is None:
                    return gr.update(), self._msg("Update failed — could not write to disk (see console).")
                return gr.update(choices=choices, value=sel), self._msg(f"Updated “{sel}”.")
            except Exception:
                traceback.print_exc()
                return gr.update(), self._msg("Update failed — see console.")

        def _delete(sel):
            if not sel:
                return gr.update(), self._msg("Pick a saved entry to delete.")
            choices = store.delete(sel)
            if choices is None:
                return gr.update(), self._msg("Delete failed — could not write to disk (see console).")
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
                # Filter the saved params on LOAD the same way Save filters them,
                # so a hand-edited / shared library file can't inject identity,
                # media, or non-scalar keys into the live settings dict.
                params = store.sanitize_params(entry.get("params"))
                if params:
                    for k, v in params.items():
                        settings[k] = v
                    applied = f" + {len(params)} parameter(s)"
                # New timestamp -> refresh_form_trigger.change -> fill_inputs rebuilds the form.
                return time.time(), self._msg(f"Populated prompts{applied} from “{sel}”.")
            except Exception:
                traceback.print_exc()
                return gr.update(), self._msg("Populate failed — see console.")

        def _on_select(sel):
            return self._msg(self._tag(store.get(sel)) if sel else "")

        # Our parent is the form's main Column, so a collapsible Accordion is the
        # right container — one new child, which the host pops + re-inserts right
        # after the Generate button.
        with gr.Accordion(f"📚 {PLUGIN_NAME}", open=False) as panel:
            gr.Markdown(_HELP)
            with gr.Row():
                pl_name = gr.Textbox(label="Name", placeholder="e.g. moody portrait", scale=2)
                pl_saved = gr.Dropdown(label="Saved prompts", choices=store.names(), value=None, scale=2)
            pl_preserve = gr.Checkbox(
                label="Preserve all parameters", value=False,
                info="Also snapshot every generation setting (steps, guidance, "
                     "resolution, seed, LoRAs…); these come from the last applied "
                     "settings, so click Generate or Save Settings first to commit "
                     "slider changes. Off = prompt + negative only (always live).",
            )
            with gr.Row():
                pl_save = gr.Button("💾 Save Current Prompts", size="sm")
                pl_update = gr.Button("⟳ Update", size="sm")
                pl_populate = gr.Button("📥 Populate Fields", variant="primary", size="sm")
                pl_delete = gr.Button("🗑 Delete", variant="stop", size="sm")
            pl_status = gr.Markdown("")  # action feedback (Saved / Deleted / errors)
            pl_tag = gr.Markdown("")     # model tag of the selected entry

            save_inputs = [state, pl_name, pl_preserve, *live_components]
            update_inputs = [state, pl_saved, pl_preserve, *live_components]
            pl_save.click(_save, inputs=save_inputs, outputs=[pl_saved, pl_status])
            pl_update.click(_update, inputs=update_inputs, outputs=[pl_saved, pl_status])
            pl_delete.click(_delete, inputs=[pl_saved], outputs=[pl_saved, pl_status])
            pl_populate.click(_populate, inputs=[state, pl_saved], outputs=[trigger, pl_status])
            # Selecting an entry updates a SEPARATE tag line, so it never clobbers
            # the Save/Delete confirmation in pl_status.
            pl_saved.change(_on_select, inputs=[pl_saved], outputs=[pl_tag])

        return panel


Plugin = MediaGenPromptLibrary
