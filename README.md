# Prompt Library — a Wan2GP plugin

A standalone, **model-agnostic prompt library** that lives right inside the
**Media Generation** tab — a collapsible panel injected just above the Lora
Profile (lset) shortcuts at the top. Save the prompts you like, recall them with
one click, and optionally carry a full set of generation parameters along for the
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

- **📚 Prompt Library panel** — a collapsible accordion at the top of the Media
  Generation tab, above the Lora Profile shortcuts.
- **💾 Save Current Prompts** — store the current prompt + negative prompt under a
  name. The entry is tagged with the model you currently have selected.
- **Preserve all parameters** *(optional tickbox)* — also snapshot every
  generation setting (steps, guidance, resolution, seed, sampler, LoRAs, sliding
  window, post-process…) so a full setup can be reproduced. Off by default →
  prompt + negative only. Reference media (start / ref images, control video /
  audio, masks) is never stored.
- **⟳ Update** — overwrite the selected entry with the current prompts (and
  parameters, if the tickbox is on).
- **📥 Populate Fields** — load the selected entry back into the Media Generation
  form: the prompt + negative always, plus every saved parameter when the entry
  was saved with *Preserve all parameters*. The model is **not** switched — the
  prompt drops onto whatever model you're on now.
- **🗑 Delete** — remove the selected entry.
- **Model tag** — the model an entry was saved for is shown beside the status line
  when you select it, so you always know its origin without it constraining use.

## How it works

The panel is injected with the host plugin API's `insert_after`, anchored to the
`image-modal-container` element so it lands immediately above the lset shortcuts
row. Saving and populating read / write the **live per-model settings dict** via
the host's `get_current_model_settings`, and a populate pings the
`refresh_form_trigger` so the form rebuilds from the updated settings — the same
plumbing the bundled `sample` plugin uses. No host files are modified.

Saved prompts persist to `.mediagen_promptlib.json` at the Wan2GP root (outside
this plugin's repo), as a single shared collection:

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
tab — the **📚 Prompt Library** accordion is at the top.

## License

WanGP Community License 2.0 — see [`LICENSE`](LICENSE). Third-party components keep
their own licenses.
