# Layers given with a datatype (stackup format 3.2: a <Layer> with a Datatype). A layer list entry is a GDS layer
# number (every datatype of that number, as always), a (layer, datatype) pair, or a gds2palace layer id with a
# datatype (68/20 is 10006800020): then only that datatype is simplified, counted or merged. A metal on 68/20 and a
# via on 68/44 share the layer number and must not be mixed.

import gdstk

from gds_geometry_utils import LayerSelection, layer_spec
from gds_simplify_for_em import estimate_polygon_count, layer_label, layers_from_stackup, run_simplify


def rect(x0, y0, x1, y1, layer, datatype):
    return gdstk.rectangle((x0, y0), (x1, y1), layer=layer, datatype=datatype)


def write_layout(path):
    """Metal 68/20: two touching rectangles. Vias 68/44: a 3 x 3 array on it, 0.5 um apart. Keepout 68/5: two
    touching rectangles that no stackup layer reads. Upper metal 69/0: two touching rectangles."""
    lib = gdstk.Library()
    cell = lib.new_cell("top")
    cell.add(rect(0, 0, 10, 10, 68, 20), rect(10, 0, 20, 10, 68, 20))
    for i in range(3):
        for j in range(3):
            cell.add(rect(2 + i, 2 + j, 2.5 + i, 2.5 + j, 68, 44))
    cell.add(rect(0, 20, 10, 30, 68, 5), rect(10, 20, 20, 30, 68, 5))
    cell.add(rect(0, 0, 10, 10, 69, 0), rect(10, 0, 20, 10, 69, 0))
    lib.write_gds(str(path))


def counts(path):
    result = {}
    for polygon in gdstk.read_gds(str(path)).top_level()[0].polygons:
        key = (polygon.layer, polygon.datatype)
        result[key] = result.get(key, 0) + 1
    return result


class Metal:
    def __init__(self, layernum, is_via=False, above=(), below=()):
        self.layernum, self.is_via, self.is_metal = layernum, is_via, not is_via
        self.above, self.below = list(above), list(below)


class Metals:
    """The part of gds2palace's metals_list that layers_from_stackup() reads."""
    def __init__(self, metals):
        self.metals = metals

    def getallplanarmetals(self):
        return [m for m in self.metals if m.is_metal]


def stackup():
    m1, m2 = Metal("10006800020"), Metal("69")          # the layer ids as the stackup reader gives them
    via = Metal("10006800044", is_via=True, above=[m2], below=[m1])
    return Metals([m1, via, m2, Metal("201")])


def test_layer_spec_forms():
    assert layer_spec(134) == (134, None) and layer_spec("134") == (134, None)
    assert layer_spec((68, 20)) == (68, 20) and layer_spec(10006800020) == (68, 20)
    assert layer_spec("10006800000") == (68, 0)          # datatype 0 given in the stackup is not "any datatype"
    selection = LayerSelection([69, (68, 20)])
    assert selection(69, 0) and selection(69, 7) and selection(68, 20)
    assert not selection(68, 44) and not selection(70, 0)
    assert 68 in selection and 69 in selection and 70 not in selection


def test_layers_from_stackup_keeps_the_datatype():
    metal_layers, via_layers = layers_from_stackup(stackup())
    assert metal_layers == [(68, 20), 69]                # port layer 201 left out
    assert via_layers == [((68, 44), [69], [(68, 20)])]
    assert [layer_label(s) for s in metal_layers] == ["68/20", "69"]


def test_polygon_count_follows_the_datatype(tmp_path):
    gds = tmp_path / "layout.gds"
    write_layout(gds)
    ids = ["10006800020", "10006800044", "69"]           # metals_list.getlayernumbers()
    assert estimate_polygon_count(str(gds), "", ids, [0]) == 2 + 9 + 2
    assert estimate_polygon_count(str(gds), "", [68], [0]) == 0      # the plain number follows the datatype list
    assert estimate_polygon_count(str(gds), "", [68], None) == 2 + 9 + 2
    assert estimate_polygon_count(str(gds), "", [(68, 20)], [0]) == 2


def test_simplify_merges_only_the_stackup_datatypes(tmp_path):
    gds, out = tmp_path / "layout.gds", tmp_path / "out.gds"
    write_layout(gds)
    metal_layers, via_layers = layers_from_stackup(stackup())
    run_simplify(str(gds), metal_layers, str(out), do_merge=True, via_layers=via_layers, via_merge_size=0.6)
    result = counts(out)
    assert result[(68, 20)] == 1                         # the metal: merged
    assert result[(69, 0)] == 1
    assert result[(68, 44)] == 1                         # the vias: one merged array, not mixed with the metal
    assert result[(68, 5)] == 2                          # not a stackup layer: untouched


def test_plain_layer_number_still_means_all_datatypes(tmp_path):
    gds, out = tmp_path / "layout.gds", tmp_path / "out.gds"
    write_layout(gds)
    run_simplify(str(gds), [68, 69], str(out), do_merge=True)
    result = counts(out)
    assert result[(68, 20)] == 1 and result[(68, 5)] == 1 and result[(69, 0)] == 1
    assert result[(68, 44)] == 9                         # separate vias stay separate when merged per layer
