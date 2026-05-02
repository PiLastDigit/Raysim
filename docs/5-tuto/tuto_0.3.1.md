# Tutorial 0.3.1 — XCAF Label Trees: Instance vs Prototype Names in STEP Files

## The Problem

You open a PCBA STEP file in RaySim and see `solid_0000` instead of `R41`. A STP viewer shows `R41`. Why?

## How STEP Files Store Names

A STEP file describes an assembly as a tree of **product definitions** (prototypes) and **product definition instances** (references). When SolidWorks exports a board with fifty 0402 resistors, it writes:

- One **prototype** called `R_0402_1005Metric` — the part shape definition
- Fifty **instances** called `R41`, `R42`, ..., `R90` — each referencing the same prototype

OCCT's XCAF framework mirrors this in a label tree:

```
Assembly label "PCBA"
  ├── Component label "R41"  (IsReference=True)
  │     └── Referred label "R_0402_1005Metric"  (IsSimpleShape=True)
  │           └── TopoDS_Solid
  ├── Component label "R42"  (IsReference=True)
  │     └── Referred label "R_0402_1005Metric"  (same prototype)
  ...
```

The **component label** carries the instance name. The **referred label** carries the prototype name. Both are `TDF_Label` objects with `GetLabelName()`.

## The Walk Pattern

When walking this tree, `ShapeTool.GetComponents()` gives you the component labels. Each one `IsReference()` — meaning it points to another label via `GetReferredShape()`. The natural thing is to follow the reference and recurse on the referred label. But the referred label's name is the prototype name, not the instance name.

```python
# component_label.GetLabelName()  →  "R41"     (instance)
# referred_label.GetLabelName()   →  "R_0402_1005Metric"  (prototype)
```

If you only call `GetLabelName()` on the referred label, you get fifty solids all named `R_0402_1005Metric`. If you only call it on the component label, you lose the part type info.

## The Solution

Capture the component name **before** following the reference, then pass it down:

```python
if shape_tool.IsReference(comp_label):
    instance_name = comp_label.GetLabelName()
    shape_tool.GetReferredShape(comp_label, ref_label)
    # recurse on ref_label, passing instance_name
```

In the recursive call, the referred label's own name becomes the prototype name. The instance name takes priority for display:

```python
proto_name = ref_label.GetLabelName()     # "R_0402_1005Metric"
name = instance_name or proto_name         # "R41"
part_name = proto_name if instance_name else None
```

This gives you both names where they matter: the instance name for human identification, the prototype name for material-rule matching.

## Why FindAttribute Doesn't Work

pythonocc wraps OCCT via SWIG. The C++ method `TDF_Label::FindAttribute(GUID, Handle<TDF_Attribute>&)` expects an output handle parameter. In pythonocc 7.9.x, passing a `TDataStd_Name()` object triggers a SWIG type mismatch:

```
Wrong number or type of arguments for overloaded function 'TDF_Label_FindAttribute'.
Possible prototypes: TDF_Label::FindAttribute(Standard_GUID const &, handle<TDF_Attribute> &)
```

`TDataStd_Name` is a subclass of `TDF_Attribute`, but SWIG's overload resolution doesn't match it to the `Handle<TDF_Attribute>&` parameter. The error is silently caught by `except Exception: pass`, making every name `None`.

`GetLabelName()` is a convenience method on `TDF_Label` that handles the attribute lookup internally in C++ — no SWIG parameter-passing issues. pythonocc's own `DataExchange.py` uses it for exactly this reason.

## Takeaway

When working with pythonocc SWIG bindings, prefer high-level convenience methods (`GetLabelName`, `GetColor`, etc.) over low-level attribute APIs (`FindAttribute`). The SWIG layer handles output parameters inconsistently, and the convenience methods avoid the issue entirely.
