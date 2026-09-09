"""Recover location evidence without mistaking the nearest job for proof.

Historical coordinates remain candidates. A location result cannot by itself
establish a photo/job link, and copied GPS-derived allocations are not a second
independent source. No network geocoding or guessed coordinates.
"""
import math
from pathlib import Path
from collection_sources import rows, sha_file, record_ref
import json


def point(row):
    try:
        lat, lon = float(row['lat']), float(row['lon'])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon
    except (KeyError, TypeError, ValueError):
        return None


def distance(a, b):
    lat1, lat2 = map(math.radians, (a[0], b[0]))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b[1]-a[1])/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


def load_geo(base):
    locations, jobs = base/'geolocations.jsonl', base/'grind/job_coords.json'
    signatures = {str(p): sha_file(p) if p.exists() else 'unavailable' for p in (locations, jobs)}
    points = {}
    for row in rows(locations):
        if row.get('path') and point(row):
            path = Path(row['path'])
            path = path if path.is_absolute() else base/path
            points.setdefault(str(path.resolve()), set()).add(point(row))
    job_rows = json.loads(jobs.read_text()) if jobs.exists() else {}
    return {'points': points, 'jobs': job_rows, 'signatures': signatures}


def location_evidence(path, geo, original=None, radius=150):
    points = {point(original)} if original and point(original) else geo['points'].get(str(Path(path).resolve()), set())
    basis = 'original EXIF' if original and point(original) else 'historical location ledger; not reverified'
    result = {'state': 'unavailable', 'basis': basis, 'candidates': [],
              'source_signatures': geo['signatures'], 'settles_job': False}
    if len(points) > 1:
        return dict(result, state='conflicting_photo_coordinates')
    if not points:
        return result
    photo_point = next(iter(points))
    if not geo['jobs']:
        return dict(result, state='job_coordinates_unavailable', latitude=photo_point[0], longitude=photo_point[1])
    candidates = []
    for raw_ref, row in geo['jobs'].items():
        ref, coords = record_ref(raw_ref), point(row)
        if ref and coords:
            metres = distance(photo_point, coords)
            if metres <= radius:
                candidates.append({'job_ref': ref, 'distance_m': round(metres, 1),
                                   'basis': 'historical job-coordinate map; not independent photo attribution'})
    return dict(result, state='ambiguous' if len(candidates)>1 else 'candidate' if candidates else 'no_nearby_job',
                latitude=photo_point[0], longitude=photo_point[1], candidates=sorted(candidates,key=lambda r:r['distance_m']))
