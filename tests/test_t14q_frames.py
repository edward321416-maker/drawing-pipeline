"""C-T14Q frame registration, camera reproduction and solar position tests."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from tools.t14q import frames

CACHE = Path(r"D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14K\output\C_T14K_run\model_cache")
OSM = Path(r"D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\02_site_analysis\data\osm_ddp.json")
SITE = OSM.parent / "site_estimate.json"
NPZ_SHA = "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b"


def test_frame_round_trips():
    x, y = 123.4, -56.7
    assert frames.cache_to_osm(*frames.osm_to_cache(x, y)) == pytest.approx((x, y))
    assert frames.local_to_cache(*frames.cache_to_local(1.0, 2.0, 3.0)) == pytest.approx((1.0, 2.0, 3.0))
    lon, lat = frames.osm_to_lonlat(-88.0, 0.0)
    assert frames.lonlat_to_osm(lon, lat) == pytest.approx((-88.0, 0.0))


def test_bearing_is_compass_clockwise_from_north():
    assert frames.bearing_deg(0, 1) == pytest.approx(0)
    assert frames.bearing_deg(1, 0) == pytest.approx(90)
    assert frames.bearing_deg(0, -1) == pytest.approx(180)
    assert frames.bearing_deg(-1, 0) == pytest.approx(270)


def test_g002_camera_reproduces_t14o_final_v2_audit():
    cam = frames.g002_camera()
    # numbers recorded in final_v2/pbr_render_audit.json
    assert cam["camera_local_m"] == pytest.approx((148.4501953125, -279.1942138671875, 144.1531982421875), abs=0.05)
    assert cam["view_bearing_deg"] == pytest.approx(332.0, abs=0.1)  # looks NNW
    assert cam["camera_bearing_from_tower_deg"] == pytest.approx(152.0, abs=0.1)  # stands SSE
    assert 18.0 < cam["pitch_down_deg"] < 19.0
    assert cam["hfov_deg"] == pytest.approx(36.2, abs=0.1)
    lon, lat = cam["camera_lonlat"]
    assert 127.008 < lon < 127.010 and 37.563 < lat < 37.565


def test_sun_position_summer_solstice_noon_seoul():
    lat, lon = 37.567, 127.0105
    start = datetime(2026, 6, 21, 2, 0, tzinfo=timezone.utc)
    samples = [(start + timedelta(minutes=m)) for m in range(0, 240)]
    best = max(samples, key=lambda t: frames.sun_position(lat, lon, t)[1])
    az, el = frames.sun_position(lat, lon, best)
    assert el == pytest.approx(90 - lat + 23.44, abs=0.35)
    assert abs(az - 180.0) < 2.0


def test_sun_rises_east_at_equinox_and_azimuth_increases_through_day():
    lat, lon = 37.567, 127.0105
    t0 = datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc)  # ~03:00 KST, before sunrise
    prev = None
    rise_az = None
    for m in range(0, 600):
        t = t0 + timedelta(minutes=m)
        az, el = frames.sun_position(lat, lon, t)
        if prev is not None and prev < 0 <= el:
            rise_az = az
            break
        prev = el
    assert rise_az is not None and abs(rise_az - 90.0) < 3.0
    az_morning = frames.sun_position(lat, lon, datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc))[0]  # 10:00 KST
    az_afternoon = frames.sun_position(lat, lon, datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc))[0]  # 15:00 KST
    assert 90 < az_morning < 180 < az_afternoon < 270


@pytest.mark.skipif(not (CACHE.exists() and OSM.exists()), reason="local verified cache / OSM extract not present")
def test_cache_context_vertices_coincide_with_osm_after_registration():
    import hashlib

    h = hashlib.sha256((CACHE / "model_world.npz").read_bytes()).hexdigest()
    if h != NPZ_SHA:
        pytest.skip("different cache build; registration constants do not apply")
    meta = json.loads((CACHE / "model_objects.json").read_text(encoding="utf-8"))
    with np.load(CACHE / "model_world.npz", allow_pickle=False) as d:
        V = d["V"]
    co = next(o for o in meta["objects"] if o["kind"] == "context_building")
    P = V[co["v0"]:co["v0"] + co["nv"]]
    base = P[P[:, 2] < 0.01][:, :2]
    osm = json.loads(OSM.read_text(encoding="utf-8"))
    pts = np.array([p for f in osm["features"] if "building" in f["tags"] and f.get("closed") for p in f["xy"]])
    pts = pts + np.array(frames.CACHE_FROM_OSM_OFFSET)
    nn = np.empty(len(base))
    for i in range(0, len(base), 128):
        blk = base[i:i + 128]
        nn[i:i + 128] = np.sqrt(((blk[:, None, :] - pts[None, :, :]) ** 2).sum(2)).min(1)
    assert np.mean(nn < 0.1) > 0.99
    assert np.median(nn) < 0.05


@pytest.mark.skipif(not SITE.exists(), reason="studio site_estimate.json not present")
def test_lot_centroid_maps_to_cache_origin():
    from shapely.geometry import Polygon

    ring = json.loads(SITE.read_text(encoding="utf-8"))["calibrated_site_xy"]
    c = Polygon(ring).centroid
    x, y = frames.osm_to_cache(c.x, c.y)
    assert math.hypot(x, y) < 0.5
