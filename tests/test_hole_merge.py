# Merging must keep the holes of a merged shape. gdstk 1.0.2 normally returns a hole linked to its outline (a keyhole
# polygon), but in some unions of many shapes it returns the hole as a separate polygon that only runs clockwise.
# GDSII has no holes, so every reader takes that polygon as metal: a 7350 um2 cut-out of a Metal1 plane came out filled.
# The 29 shapes below are the smallest set from a real layout (FMD_QNC_amps_filled.gds, Metal1) that still shows it.

import numpy as np
import pytest
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

import gds_prepare_for_EM as prepare

SHAPES = [(-200.0, -366.0, -197.0, 306.0), (-159.205, 240.0, -91.505, 261.5), (-197.505, -305.0, -195.005, -300.0),
          (-193.005, -310.7, -132.705, -307.0), (-193.405, -333.9, -79.675, -310.7), (-197.505, 211.8, -91.505, 234.9),
          (-159.205, 261.5, -91.505, 266.4), (-132.39, 266.4, -130.805, 269.85), (-125.89, 266.4, -124.305, 269.85),
          [(-143.555, 268.6), (-142.555, 268.6), (-142.555, 274.6), (-120.605, 274.6), (-120.605, 268.5),
           (-119.605, 268.5), (-119.605, 275.6), (-143.555, 275.6)],
          (-118.405, -310.7, -79.675, -308.4), (-118.405, -308.4, -113.505, -302.1), (-195.005, -360.0, -193.005, -300.0),
          (-87.5, 222.5, -57.5, 252.5), (-92.5, 247.5, -87.5, 252.5), (-92.5, 222.5, -87.5, 227.5),
          (-92.5, 257.5, -87.5, 262.5), (-77.5, -312.5, -47.5, -282.5), (-82.5, -282.5, -72.5, -277.5),
          (-82.5, -312.5, -77.5, -307.5), (-122.5, -242.5, -92.5, -212.5), (-127.5, -242.5, -122.5, -237.5),
          (-192.5, -242.5, -162.5, -212.5), (-197.5, -242.5, -192.5, -237.5), (-157.5, -242.5, -127.5, -212.5),
          (-162.5, -242.5, -157.5, -237.5), (-92.5, -242.5, -87.5, -237.5), (-87.5, -277.5, -57.5, -247.5),
          (-92.5, -247.5, -82.5, -242.5)]
IN_THE_HOLE = Point(-142.25, -262.5)


def points():
    return [np.array([(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]) if isinstance(r, tuple) else np.array(r)
            for r in SHAPES]


def test_merged_shape_keeps_its_hole():
    expected = unary_union([box(*r) if isinstance(r, tuple) else Polygon(r) for r in SHAPES])
    assert sum(len(g.interiors) for g in expected.geoms) == 1 and not expected.contains(IN_THE_HOLE)
    merged = prepare.merge_polygons(points())
    # read as GDSII readers do: every polygon is metal, whatever its direction
    shapes = [Polygon(p).buffer(0) for p in merged]
    assert not any(s.contains(IN_THE_HOLE) for s in shapes), "the hole was filled"
    assert unary_union(shapes).area == pytest.approx(expected.area, rel=1e-9)
    assert sum(s.area for s in shapes) == pytest.approx(expected.area, rel=1e-9), "pieces overlap"


def test_island_inside_the_hole_stays():
    island = (-180.0, -300.0, -170.0, -290.0)
    shapes = SHAPES + [island]
    merged = prepare.merge_polygons(points() + [np.array([(-180, -300), (-170, -300), (-170, -290), (-180, -290)])])
    pieces = [Polygon(p).buffer(0) for p in merged]
    assert any(s.contains(Point(-175, -295)) for s in pieces), "the island was cut out with the hole"
    assert not any(s.contains(IN_THE_HOLE) for s in pieces)
    expected = unary_union([box(*r) if isinstance(r, tuple) else Polygon(r) for r in shapes])
    assert unary_union(pieces).area == pytest.approx(expected.area, rel=1e-9)


def test_keyhole_results_are_left_alone():
    """the usual case: gdstk links the hole to its outline, nothing to repair"""
    frame = [np.array([(0, 0), (10, 0), (10, 2), (0, 2)]), np.array([(0, 8), (10, 8), (10, 10), (0, 10)]),
             np.array([(0, 0), (2, 0), (2, 10), (0, 10)]), np.array([(8, 0), (10, 0), (10, 10), (8, 10)])]
    merged = prepare.merge_polygons(frame)
    assert len(merged) == 1 and abs(prepare._signed_area(merged[0])) == pytest.approx(64.0)
