"""Adapter to the existing Mini A identity ladder.

This module does not resolve jobs itself. It loads fewshot_engine
(the existing ladder) and records the lanes that engine used.

Filing rules applied here, on top of the ladder result:
- never mint a job
- never treat date as an identity lane
- require two supporting lanes before final filing, unless Lee already answered
- album title may be one lane; folder staging is not a lane
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from . import paths

log = logging.getLogger("image_plane.identity")

JOB_REF_RE = re.compile(r"\b(\d{3,5}-\d{2})\b")
_ENGINE = None
_ENGINE_ERROR = None


def extract_job_ref(text: str | None) -> str | None:
    if not text:
        return None
    m = JOB_REF_RE.search(str(text))
    return m.group(1) if m else None


def ladder_base() -> Path:
    env = os.environ.get("IMAGE_PLANE_LADDER_BASE")
    if env:
        return Path(env).expanduser()
    return paths.root()


def _engine_candidates() -> list[Path]:
    env = os.environ.get("IMAGE_PLANE_LADDER_MODULE")
    if env:
        return [Path(env).expanduser()]
    out = []
    base = ladder_base()
    out.extend(
        [
            base / "fewshot_engine.py",
            base / "scripts" / "mini_a" / "fewshot_engine.py",
            Path(__file__).resolve().parents[2] / "scripts" / "mini_a" / "fewshot_engine.py",
        ]
    )
    seen = set()
    unique = []
    for p in out:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def load_engine():
    """Import the existing ladder module. Never copy its resolve logic."""
    global _ENGINE, _ENGINE_ERROR
    if _ENGINE is not None:
        return _ENGINE
    if _ENGINE_ERROR is not None and os.environ.get("IMAGE_PLANE_LADDER_RETRY") != "1":
        return None
    last_err = None
    for path in _engine_candidates():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("fewshot_engine_live", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules["fewshot_engine_live"] = mod
            spec.loader.exec_module(mod)
            for name in ("resolve_job", "load_ladder_sources", "location_lane", "named_job"):
                if not hasattr(mod, name):
                    raise RuntimeError(f"ladder module missing {name}: {path}")
            _ENGINE = mod
            _ENGINE_ERROR = None
            log.info("identity ladder loaded from %s", path)
            return _ENGINE
        except Exception as e:
            last_err = e
            log.warning("could not load ladder at %s: %s", path, e)
    _ENGINE_ERROR = last_err or RuntimeError(
        "identity ladder not found; checked " + ", ".join(str(p) for p in _engine_candidates())
    )
    return None


def ladder_error() -> str | None:
    if _ENGINE is not None:
        return None
    load_engine()
    if _ENGINE_ERROR is None:
        return None
    return str(_ENGINE_ERROR)


def _point_from_row(row: dict) -> tuple[float, float] | None:
    lat, lon = row.get("gps_lat"), row.get("gps_lon")
    if lat is None or lon is None:
        return None
    try:
        return (float(lat), float(lon))
    except (TypeError, ValueError):
        return None


def call_ladder(
    row: dict,
    *,
    album_title: str | None = None,
    sources: dict | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Call the existing ladder and return structured evidence.

    `row` must not carry a guessed job_ref. Album-extracted refs stay
    outside resolve_job so they cannot trip the Lee-answer exemption.
    """
    base = base or ladder_base()
    engine = load_engine()
    evidence: dict[str, Any] = {
        "lanes": [],
        "album_title": None,
        "date_used_for_identity": False,
        "ladder_available": engine is not None,
        "ladder_result": None,
        "reason": None,
        "filed_job_ref": None,
        "may_file": False,
    }

    extracted = extract_job_ref(album_title)
    if album_title:
        evidence["album_title"] = {
            "title": album_title,
            "extracted_ref": extracted,
            "used_as_lane": bool(extracted),
        }
        if extracted:
            evidence["lanes"].append(
                {
                    "name": "album_title",
                    "job_ref": extracted,
                    "detail": f"album title {album_title!r}",
                }
            )

    if engine is None:
        evidence["identity_status"] = "ladder_blocked"
        evidence["reason"] = ladder_error() or "identity ladder unavailable"
        return evidence

    try:
        if sources is None:
            sources = engine.load_ladder_sources(base)
        # Strip any job_ref so album/folder hints cannot become lee_answer.
        safe_row = dict(row)
        safe_row.pop("job_ref", None)
        safe_row.pop("job", None)
        result = engine.resolve_job(
            safe_row,
            sources.get("register") or {},
            sources.get("points") or {},
            sources.get("located_jobs") or {},
            base,
        )
        evidence["ladder_result"] = result
        evidence["ladder_sources"] = sources.get("source_counts", {})
        evidence["absent_sources"] = sources.get("absent_sources", [])

        method = str((result or {}).get("method") or "")
        job_ref = (result or {}).get("job_ref")
        if job_ref and method:
            if method == "lee_answer":
                evidence["lanes"].append(
                    {
                        "name": "lee_answer",
                        "job_ref": job_ref,
                        "detail": "Lee already named this picture",
                    }
                )
            else:
                for part in method.split("+"):
                    part = part.strip()
                    if not part:
                        continue
                    evidence["lanes"].append(
                        {
                            "name": part,
                            "job_ref": job_ref,
                            "detail": f"ladder method {method}",
                        }
                    )

        point = _point_from_row(row)
        by_location = engine.location_lane(point, sources.get("located_jobs") or {})
        if by_location:
            already = any(l.get("name") == "lane2_gra_sites" for l in evidence["lanes"])
            if not already:
                metres = None
                loc = (sources.get("located_jobs") or {}).get(by_location) or {}
                if point and loc.get("lat") is not None:
                    metres = engine.metres_apart(point, (float(loc["lat"]), float(loc["lon"])))
                evidence["lanes"].append(
                    {
                        "name": "lane2_gra_sites",
                        "job_ref": by_location,
                        "detail": "position lane from existing located-job map",
                        "metres": metres,
                    }
                )
        if (result or {}).get("reason"):
            evidence["reason"] = result["reason"]
    except Exception as e:
        evidence["identity_status"] = "ladder_blocked"
        evidence["reason"] = f"ladder call failed: {type(e).__name__}: {e}"
        evidence["ladder_available"] = False
        return evidence

    decision = decide_filing(evidence)
    evidence.update(decision)
    return evidence


def decide_filing(evidence: dict) -> dict:
    """Two supporting lanes, same job. Date is never a lane. No minting."""
    lanes = [l for l in evidence.get("lanes") or [] if l.get("job_ref")]
    by_job: dict[str, list[dict]] = {}
    for lane in lanes:
        by_job.setdefault(lane["job_ref"], []).append(lane)

    lee = next((l for l in lanes if l.get("name") == "lee_answer"), None)
    if lee:
        return {
            "may_file": True,
            "filed_job_ref": lee["job_ref"],
            "identity_status": "resolved",
            "reason": None,
        }

    for job_ref, group in by_job.items():
        names = {l["name"] for l in group}
        if len(names) >= 2:
            return {
                "may_file": True,
                "filed_job_ref": job_ref,
                "identity_status": "resolved",
                "reason": None,
            }

    if not lanes:
        return {
            "may_file": False,
            "filed_job_ref": None,
            "identity_status": "quarantined",
            "reason": evidence.get("reason") or "No recorded lane found a job.",
        }
    named = ", ".join(sorted({l["name"] for l in lanes}))
    return {
        "may_file": False,
        "filed_job_ref": None,
        "identity_status": "quarantined",
        "reason": evidence.get("reason")
        or f"Only one supporting identity lane ({named}). Two lanes are required.",
    }


def dump_evidence(evidence: dict) -> str:
    return json.dumps(evidence, default=str, sort_keys=True)
