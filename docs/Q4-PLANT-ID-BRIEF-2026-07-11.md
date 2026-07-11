# BRIEF — Q4 plant/moss IDs (lee_followups items 15–20), 2026-07-11

Doer: sonnet. Vision model: LOCAL qwen3-vl via Ollama on Mini A ONLY
(`ssh macminia@192.168.178.61`). Photo bytes never leave Mini A — run the model THERE
(curl 127.0.0.1:11434 on Mini A over ssh), never copy images to the laptop.

## Ollama gotchas (priced-in, do not rediscover)
- `think:false` → EMPTY output on qwen3-vl. Leave thinking on; parse the text answer.
- NO `format:json` support — ask for a fenced plain-text block and parse it yourself.
- ALWAYS set `num_ctx: 4096` explicitly (default 256k ctx = 48GB = kills the box).
- If ollama isn't up: `~/image-plane/start_ollama.sh`. NEVER kill a running ollama.
- ~20s/image is normal. 12 images ≈ 5 min. Sequential, not parallel.

## The asks (image paths verified this session; base64 the file into the Ollama call)
| Item | Images (on Mini A) | Ask |
|---|---|---|
| 15 | c1: `icloud-export-2026-06/2016/08/22/IMG_2979.JPG`, `IMG_2982.JPG`, `IMG_2987.JPG` | Lee: "crassula-coloured plant that is NOT crassula — ID wanted". Offer top-3 candidates w/ confidence /100 each. |
| 16 | c2: `2016/11/07/IMG_3439.JPG` | "long mat-forming clumps" — species ID, top-3 w/ conf. |
| 17 | c4: `2020/08/12/IMG_7930.HEIC` | CONFIRM/DENY: corncockle, cornflower, oxeye daisy each present? conf /100 per species. |
| 18 | c7: `2020/10/01/IMG_8178.HEIC` | near-ground plant ID, top-3 w/ conf. |
| 19 | c8: `2025/05/16/IMG_7245.HEIC` | ID requested (unspecified) — describe + top-3 w/ conf. |
| 20 | c12 (moss): `2019/10/15/IMG_8158.HEIC`, `IMG_8159.HEIC`, `IMG_8160.HEIC`, `IMG_8165.HEIC`, `IMG_8166.HEIC` | Moss IDs incl. the "cup on a long stand" form (Lee's phrase — likely a stalked/pedicellate structure; consider Polytrichum, splash-cup forms, capsule-on-seta). Real candidate IDs w/ conf /100, per image. |

## Hard rules
- **Invasive-first**: for every image, FIRST state any invasive/threat species visible
  (or "no invasive threat seen"), THEN the ID answer.
- **Sedum**: if sedum present, each species named individually w/ conf /100 — never "mixed sedum".
- HEIC: qwen3-vl via Ollama needs JPEG — convert ON MINI A with
  `sips -s format jpeg -s formatOptions 85 <src> --out /tmp/q4_NN.jpg` (verify first
  bytes ffd8), feed the jpg, delete /tmp copies after.
- Output = MODEL OPINION, never ground truth: write findings to laptop
  `~/image-plane/docs/Q4-PLANT-ID-FINDINGS-2026-07-11.md`, every ID labelled
  "model: qwen3-vl (local), conf N/100" — nothing enters knowledge_notes, guards, or any
  Lee/client surface. Lee's dictation loop decides what sticks.
- If the model refuses/rambles/gives empty: note it honestly per image, move on. 3
  consecutive infra failures = stop and report.
- Return: per item, one-line best answer + confidence.
