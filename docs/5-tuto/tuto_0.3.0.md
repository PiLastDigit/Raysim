# Tutorial 0.3.0 — XCAF Document Framework and the STEP Metadata Pipeline

## Why two STEP readers?

OpenCASCADE offers two ways to read a STEP file:

1. **`STEPControl_Reader`** — the "classic" reader. It transfers geometry
   (solids, shells, faces) into a `TopoDS_Shape` compound. Fast, simple,
   but carries *no metadata*: part names, colors, material annotations, and
   assembly structure are all lost.

2. **`STEPCAFControl_Reader`** — the XCAF ("eXtended CAD Framework") reader.
   It transfers both geometry *and* metadata into a `TDocStd_Document`, which
   is an in-memory tree of labelled shapes. Each label can carry attributes:
   `TDataStd_Name` (string name), `XCAFDoc_Color` (RGB), `XCAFDoc_Material`
   (material name + density), and structural information (assembly/component
   relationships).

RaySim's Phase B1 used `STEPControl_Reader` for geometry loading, and a
*separate* `STEPCAFControl_Reader` pass in `step_tags.py` to extract material
hints. This two-reader approach required a fragile correlation step: matching
XCAF leaves to geometry leaves by count + bounding-box fingerprint.

Phase B3.0 eliminates this by switching `step_loader.py` to `STEPCAFControl_Reader`
as the single reader. Geometry and metadata arrive together in one pass.

## The XCAF label tree

After `reader.Transfer(handle)`, the document's main label holds the assembly
tree. The key tools:

```python
shape_tool = XCAFDoc_DocumentTool.ShapeTool(handle.Main())
color_tool = XCAFDoc_DocumentTool.ColorTool(handle.Main())
mat_tool   = XCAFDoc_DocumentTool.MaterialTool(handle.Main())
```

Walking the tree starts with `shape_tool.GetFreeShapes()` — the top-level
shapes not referenced by any assembly. For each label:

- `shape_tool.IsAssembly(label)` — the label has components (children).
  `GetComponents()` returns them. Components may be *references* to other
  labels (`IsReference`), which need `GetReferredShape` to resolve.

- `shape_tool.IsSimpleShape(label)` — the label is a leaf. `GetShape()`
  returns the `TopoDS_Shape`. If it's a `TopAbs_SOLID`, it's a leaf solid;
  if it's a `TopAbs_COMPOUND`, it may contain multiple solids.

## Metadata extraction

Once you have a label, metadata is straightforward:

```python
# Name
from OCC.Core.TDataStd import TDataStd_Name
name_attr = TDataStd_Name()
label.FindAttribute(TDataStd_Name.GetID(), name_attr)
name = str(name_attr.Get().ToExtString())

# Color
from OCC.Core.Quantity import Quantity_Color
from OCC.Core.XCAFDoc import XCAFDoc_ColorGen
c = Quantity_Color()
color_tool.GetColor(label, XCAFDoc_ColorGen, c)
rgb = (c.Red(), c.Green(), c.Blue())

# Material
from OCC.Core.TCollection import TCollection_HAsciiString
name = TCollection_HAsciiString("")
mat_tool.GetMaterial(label, name, desc, density, ...)
material_name = str(name.String())
```

## The simplification payoff

With metadata riding alongside geometry on `LeafSolid`, `step_tags.py`
becomes a trivial mapping function:

```python
def extract_step_tags(leaves):
    return [
        StepMaterialTag(
            solid_id=leaf.solid_id,
            material_name=leaf.material_hint,
            color_rgb=leaf.color_rgb,
        )
        for leaf in leaves
    ]
```

No OCC imports. No second file read. No correlation verification. The
complexity of the two-gate verification (count check + per-leaf bbox
fingerprint) simply disappears.

## DFS order stability

The one critical invariant: `solid_id` assignment must be stable across
the migration. Project files key material assignments on `solid_id`, so
a walk-order change would corrupt existing projects.

The XCAF tree walk uses the same DFS order as the old `TopoDS_Iterator`
walk — labels are visited in the order `GetComponents` returns them,
and solids within compounds are visited by `TopoDS_Iterator` sub-walk.
The regression test (`test_dfs_order_regression`) generates a golden
fixture on first run and asserts exact match on subsequent runs.
