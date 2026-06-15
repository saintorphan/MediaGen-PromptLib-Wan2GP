# Prompt Library — a Wan2GP plugin

A standalone, **model-agnostic prompt library** that lives right inside the
**Media Generation** tab — a collapsible **📚 Prompt Library** panel directly
below the **Generate** button. Save the prompts you like, recall them with one
click, and optionally carry a full set of generation parameters along for the
ride.

Unlike the Lora Profile shortcuts (which are tied to LoRA sets), the Prompt
Library is a flat, reusable list of named prompts that works across every model.

## Why it's separate from the model

Prompts are **not** model-specific. When you save an entry, the library *tags* it
with the model you had selected at the time — but that's just a note about what
the prompt was *made for*. **Populate Fields** loads any entry onto whatever model
is currently selected, so a prompt you wrote for one model is one click away from
being tried on another. *"What it was meant for doesn't mean that's all it can be
used for."*

## Features

- **📚 Prompt Library panel** — a collapsible panel in the Media Generation tab,
  directly below the Generate button.
- **💾 Save Current Prompts** — store the current prompt + negative prompt under a
  name. The prompt + negative are read **live** from the boxes, so what you've
  just typed is what gets saved. The entry is tagged with the model you currently
  have selected. Saving under an existing name overwrites it (the status says
  *Overwrote*); there's no separate rename — save under a new name and delete the
  old one.
- **Preserve all parameters** *(optional tickbox)* — also snapshot every
  generation setting (steps, guidance, resolution, seed, sampler, LoRAs, sliding
  window, post-process…) so a full setup can be reproduced. Off by default →
  prompt + negative only. Reference media (start / ref images, control video /
  audio, masks) is never stored. **Note:** unlike the prompt + negative, these
  parameters are taken from the *last applied* settings, so click **Generate** or
  **Save Settings** first to commit any slider changes you want captured.
- **⟳ Update** — overwrite the selected entry with the current prompts (and
  parameters, if the tickbox is on).
- **📥 Populate Fields** — load the selected entry back into the Media Generation
  form: the prompt + negative always, plus every saved parameter when the entry
  was saved with *Preserve all parameters*. The model is **not** switched — the
  prompt drops onto whatever model you're on now. Because preserved parameters
  aren't model-specific, populating a *preserve-all* entry applies that entry's
  settings wholesale onto the current model (identity and media keys are filtered
  out); adjust anything that doesn't fit the new model before generating.
- **🗑 Delete** — remove the selected entry.
- **Model tag** — selecting a saved entry shows, on its own line below the status
  message, the model the entry was saved for, so you always know its origin
  without it constraining use.

## How it works

The panel is injected with the host plugin API's `insert_after`. The host
resolves the target against the **local variable names** of `generate_media_tab`
(it passes `locals()` as the component map), so the anchor is `generate_btn` —
the "Generate" button, whose parent is the form's main column. Inserting a
sibling there drops our collapsible panel directly below it. **Save** reads the
live `prompt` / `negative_prompt` textboxes directly (requested as components) so
it captures what's typed, plus the last-applied settings via the host's
`get_current_model_settings` when *Preserve all parameters* is on. **Populate**
writes the per-model settings dict and pings `refresh_form_trigger` so the form
rebuilds from the updated settings. No host files are modified.

Saved prompts persist to `.mediagen_promptlib.json` at the Wan2GP root (outside
this plugin's repo), as a single shared collection. Writes are atomic (temp file
+ `os.replace`) and an unreadable file is backed up rather than overwritten, so a
crash or bad hand-edit can't silently wipe your library; a failed write reports
an error instead of a false "saved":

```json
{
  "prompts": {
    "moody portrait": {
      "prompt": "…",
      "negative_prompt": "…",
      "model_type": "flux_dev",
      "model_name": "Flux Dev",
      "preserve": true,
      "params": { "num_inference_steps": 30, "guidance_scale": 3.5, "...": "..." }
    }
  }
}
```

## Install

Use the Wan2GP **Plugin Manager → add from GitHub URL** flow with this repo's
URL, then enable **Prompt Library** and restart Wan2GP. Open the Media Generation
tab — the collapsible **📚 Prompt Library** panel sits directly below the
Generate button.

## License

WanGP Community License 2.0 — see [`LICENSE`](LICENSE). Third-party components keep
their own licenses.
