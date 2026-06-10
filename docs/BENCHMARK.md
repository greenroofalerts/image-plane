# Caption benchmark — 2026-06-09

Measured on this MacBook (Apple M4, 24 GB, Mac16,13), Ollama 0.30.7
standalone binary (Metal backend), model **qwen2.5vl:3b** (3.2 GB
download). 10 synthetic 640×480 JPEGs, JSON caption + tags per image,
`num_predict=200`, temperature 0.2.

| metric | value |
|---|---|
| seconds per image (mean) | **7.13** |
| fastest / slowest | 6.27 / 9.34 |
| errors | 0 / 10 |
| caption accuracy spot-check | 10/10 scenes correctly described (colour, shape, count) |

The slowest image includes first-call model load; steady state is
~6.5–7 s. Real photographs are busier than synthetic scenes, so treat
**~7–9 s/image** as the planning number.

## Full-library runtime estimates (this MacBook, sequential)

| library size | runtime at 7.1 s/image |
|---|---|
| 10,000 photos | ~20 hours |
| 25,000 photos | ~49 hours |
| 50,000 photos | ~99 hours |

The caption stage is resumable (commits per image), so this can run in
overnight chunks. Options if that's too slow: run on a Mini in
parallel by pointing at the same folder split into shards, shrink
`num_predict`, or drop to a smaller model (moondream, 1.7 GB) at a
real quality cost.

## Model choice

`qwen2.5vl:3b` over `qwen2.5vl:7b` (6 GB) because the machine had only
~12 GB free disk at build time and the 3B is roughly 2× faster per
image — which dominates total cost over a whole library. The harness
auto-detects any installed vision model (qwen3-vl, qwen2.5vl, gemma3,
llama3.2-vision, minicpm-v, llava, moondream) and prefers the best
family, so upgrading later is just `ollama pull` + re-run.
