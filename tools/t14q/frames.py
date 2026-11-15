"""Coordinate frames, G-002 camera and sun for the C-T14Q Site Context pipeline.

Frames (all metres unless noted)
  OSM-local  : x East, y North, origin lon/lat = OSM_ORIGIN (studio ``osm_ddp.json``).
  cache-world: x East, y North, z up; origin = centroid of the OSM-estimated lot.
               ``cache_xy = osm_xy + CACHE_FROM_OSM_OFFSET`` (rotation 0, no mirror).
               Verified 2026-11-15: all 892 base vertices of the cache's merged
               ``context_building`` object coincide with OSM building vertices within
               0.1 m, and an edge-orientation fit selects 0 deg (score 0.977 vs ~0.2 at +-63.2).
  local      : cache-world minus ``LOCAL_ORIGIN`` (the T14O Blender scene shift).

Everything here is derived from files; nothing is surveyed.  The OSM extract is
dated 2026-10-26 and road widths/lot edges derived from it are estimates.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

# --- OSM-local frame (studio data/osm_ddp.json) ------------------------------
OSM_ORIGIN_LON = 127.0105
OSM_ORIGIN_LAT = 37.567
KX = 88236.78836212262  # metres per degree longitude at the origin latitude
KY = 110540.0           # metres per degree latitude

# --- registration of the verified model cache to OSM-local -------------------
CACHE_FROM_OSM_OFFSET = (270.030, 32.811)  # cache_xy = osm_xy + offset

# --- T14O Blender scene (final_v2 audit): local = cache_world - LOCAL_ORIGIN --
LOCAL_ORIGIN = (0.08349609375, 20.123502731323242, -16.5)
GROUND_Z_LOCAL = 16.5004  # 1F slab elevation (0.0004 m) expressed in local z

# --- T14O camera parameters (defaults used by final_v2) -----------------------
CAMERA_AZIMUTH_DEG = 62.0
CAMERA_TARGET_HEIGHT_RATIO = 0.42
CAMERA_HEIGHT_RATIO = 1.55
CAMERA_DISTANCE_SCALE = 3.4
CAMERA_LENS_MM = 55.0
SOURCE_HEIGHT_M = 93.00205993652344  # architecture bbox z span (includes B2)


def osm_to_cache(x: float, y: float) -> tuple[float, float]:
    return x + CACHE_FROM_OSM_OFFSET[0], y + CACHE_FROM_OSM_OFFSET[1]


def cache_to_osm(x: float, y: float) -> tuple[float, float]:
    return x - CACHE_FROM_OSM_OFFSET[0], y - CACHE_FROM_OSM_OFFSET[1]


def cache_to_local(x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
    return x - LOCAL_ORIGIN[0], y - LOCAL_ORIGIN[1], z - LOCAL_ORIGIN[2]


def local_to_cache(x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
    return x + LOCAL_ORIGIN[0], y + LOCAL_ORIGIN[1], z + LOCAL_ORIGIN[2]


def osm_to_lonlat(x: float, y: float) -> tuple[float, float]:
    return OSM_ORIGIN_LON + x / KX, OSM_ORIGIN_LAT + y / KY


def lonlat_to_osm(lon: float, lat: float) -> tuple[float, float]:
    return (lon - OSM_ORIGIN_LON) * KX, (lat - OSM_ORIGIN_LAT) * KY


def cache_to_lonlat(x: float, y: float) -> tuple[float, float]:
    return osm_to_lonlat(*cache_to_osm(x, y))


def bearing_deg(dx: float, dy: float) -> float:
    """Compass bearing (deg clockwise from North) of an East/North vector."""
    return math.degrees(math.atan2(dx, dy)) % 360.0


def g002_camera() -> dict:
    """Reproduce the T14O final_v2 camera analytically (no Blender needed).

    Returns world(cache) and local positions, horizontal view bearing, pitch and FOV.
    """
    h = SOURCE_HEIGHT_M
    size_xy = 72.55  # unused when distance_scale dominates (kept for parity)
    dist = max(size_xy * 2.8, h * CAMERA_DISTANCE_SCALE)
    az = math.radians(CAMERA_AZIMUTH_DEG)
    cam_local = (math.cos(az) * dist, -math.sin(az) * dist, h * CAMERA_HEIGHT_RATIO)
    target_local = (0.0, 0.0, h * CAMERA_TARGET_HEIGHT_RATIO)
    cam_world = local_to_cache(*cam_local)
    vx, vy = target_local[0] - cam_local[0], target_local[1] - cam_local[1]
    horiz = math.hypot(vx, vy)
    pitch = math.degrees(math.atan2(cam_local[2] - target_local[2], horiz))  # looking down
    sensor = 36.0
    hfov = 2 * math.degrees(math.atan(sensor / 2 / CAMERA_LENS_MM))
    vfov = 2 * math.degrees(math.atan((sensor * 9 / 16) / 2 / CAMERA_LENS_MM))
    lon, lat = cache_to_lonlat(cam_world[0], cam_world[1])
    return {
        "camera_local_m": cam_local,
        "camera_cache_world_m": cam_world,
        "camera_lonlat": (lon, lat),
        "camera_height_above_1F_m": cam_world[2] - 0.0004,
        "view_bearing_deg": bearing_deg(vx, vy),
        "camera_bearing_from_tower_deg": bearing_deg(-vx, -vy),
        "pitch_down_deg": pitch,
        "hfov_deg": hfov,
        "vfov_deg": vfov,
        "horizontal_distance_to_tower_axis_m": horiz,
    }


def sun_position(lat: float, lon: float, when_utc: datetime) -> tuple[float, float]:
    """Solar azimuth (deg clockwise from North) and elevation (deg), NOAA algorithm."""
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    when_utc = when_utc.astimezone(timezone.utc)
    jd = (when_utc - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0
    n = jd  # days since J2000.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24.0
    lst = math.radians(((gmst + lon / 15.0) % 24.0) * 15.0)
    ha = lst - ra
    phi = math.radians(lat)
    sin_el = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(ha)
    el = math.asin(sin_el)
    az = math.atan2(-math.sin(ha) * math.cos(dec),
                    math.cos(phi) * math.sin(dec) - math.sin(phi) * math.cos(dec) * math.cos(ha))
    return math.degrees(az) % 360.0, math.degrees(el)
