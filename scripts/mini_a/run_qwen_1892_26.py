#!/usr/bin/env python3
"""Run the recorded Qwen describe route on 1892-26 cabinet photos.

Route reused from describe_takeout_v2.py (27 Jul 2026): qwen3-vl:latest,
sips -> 1024 JPEG, POST /api/generate, think:false, temperature 0.
Writes one JSONL record per photo to qwen_readings.jsonl in the job folder,
and PATCHes the matching visual_observations row (raw_response, model_name,
prompt, described_at) through the same PostgREST route job_screen.py uses.
Videos are never sent. Re-run safe: skips stems already in the ledger.

Usage: python3 run_qwen_1892_26.py IMG_1843 IMG_1846 IMG_1858   (named stems)
       python3 run_qwen_1892_26.py --all                         (all photos)
"""
import base64, json, os, subprocess, sys, time, urllib.request, urllib.parse

ROOT = os.path.expanduser("~/image-plane")
ORIG = os.path.join(ROOT, "cabinet", "1892-26", "originals")
JOB_DIR = os.path.join(ROOT, "incoming", "google", "1892-26")
LEDGER = os.path.join(JOB_DIR, "qwen_readings.jsonl")
ENV_PATH = os.path.join(ROOT, ".env.flip")
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = "qwen3-vl:latest"
PROMPT = ("Describe this photograph in 1-2 factual sentences: "
          "the main subject, the setting, and whether it is indoors or outdoors.")
PROMPT_VERSION = "describe_takeout_v2/1"

def load_env(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip("\"'")
    return out

def done_stems():
    out = set()
    if os.path.exists(LEDGER):
        for l in open(LEDGER):
            try: out.add(json.loads(l)["stem"])
            except Exception: pass
    return out

def read_one(stem):
    name = None
    for ext in (".jpg", ".jpeg", ".HEIC", ".heic", ".JPG"):
        if os.path.isfile(os.path.join(ORIG, stem + ext)):
            name = stem + ext; break
    if not name:
        return None, "no-photo-file"
    src = os.path.join(ORIG, name)
    jpg = "/tmp/_q1892_%s.jpg" % stem
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1024", src, "--out", jpg],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        return None, "sips-failed"
    b = base64.b64encode(open(jpg, "rb").read()).decode()
    os.remove(jpg)
    body = json.dumps({"model": MODEL, "prompt": PROMPT, "images": [b],
                       "stream": False, "think": False,
                       "options": {"temperature": 0}}).encode()
    t0 = time.time()
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request(OLLAMA + "/api/generate", data=body,
                               headers={"Content-Type": "application/json"}),
        timeout=300).read())
    text = (resp.get("response") or "").strip()
    return {"stem": stem, "file": name, "model": MODEL, "prompt": PROMPT,
            "prompt_version": PROMPT_VERSION, "response": text,
            "seconds": round(time.time() - t0, 1),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, "ok"

def patch_vo(env, stem, rec):
    url = env.get("LEEOSPLUS_URL", "").rstrip("/")
    key = env.get("LEEOSPLUS_SERVICE_KEY", "")
    if not url or not key:
        return "no-env"
    h = {"apikey": key, "Authorization": "Bearer " + key,
         "Content-Type": "application/json"}
    q = ("job_ref=eq.1892-26&original_path=like.*" +
         urllib.parse.quote(stem) + ".jpg")
    patch = {"raw_response": rec["response"], "model_name": rec["model"],
             "prompt": rec["prompt"] + " [" + rec["prompt_version"] + "]",
             "described_at": rec["ts"]}
    req = urllib.request.Request(
        url + "/rest/v1/visual_observations?" + q,
        data=json.dumps(patch).encode(), headers=h, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return "vo-%s" % resp.status
    except Exception as e:
        return "vo-fail-%s" % type(e).__name__

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    if args == ["--all"]:
        stems = sorted({os.path.splitext(n)[0] for n in os.listdir(ORIG)
                        if n.lower().endswith((".jpg", ".jpeg", ".heic"))})
    else:
        stems = args
    env = load_env(ENV_PATH)
    done = done_stems()
    for stem in stems:
        if stem in done:
            print(stem, "already-read"); continue
        rec, status = read_one(stem)
        if not rec:
            print(stem, status); continue
        rec["vo_patch"] = patch_vo(env, stem, rec)
        with open(LEDGER, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(stem, "%.0fs" % rec["seconds"], rec["vo_patch"], "::", rec["response"][:110])

if __name__ == "__main__":
    main()
