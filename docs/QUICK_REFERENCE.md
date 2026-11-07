# Weave Object Data Preparation - Quick Reference

This document provides a quick reference for preparing custom object data for Weave.

## 📋 Required Files

For each object, you need:

```
your_object/
├── your_object.usd          # 3D model (USD format for Isaac Sim)
├── surface.npy              # Surface sample points (512, 3)
└── sdf_128.npz             # Signed Distance Field (128³ grid)
```

## 🚀 Quick Start

### Step 1: Convert STL to USD

**Option A: Using Blender (Recommended)**
```
1. Open Blender
2. File → Import → STL → Select your STL file
3. If needed: Scale object (Object → Scale → Apply)
4. File → Export → USD → Save as your_object.usd
```

**Option B: Using Script**
```bash
python scripts/convert_mesh_to_usd.py \
    --input your_object.stl \
    --output your_object.usd \
    --scale 0.001  # mm to m: 0.001, cm to m: 0.01
```

### Step 2: Generate surface.npy and sdf_128.npz

```bash
python scripts/generate_object_data.py \
    --mesh your_object.stl \
    --output ./your_object_data \
    --name your_object
```

⚠️ **Important:** Use the same scale for both USD and data generation!

### Step 3: Validate Data

```bash
python scripts/validate_object_data.py \
    --object your_object \
    --objects-dir ./your_object_data \
    --visualize
```

### Step 4: Deploy Files

```bash
# Create object directory
mkdir -p source/g1_hoi_learning/g1_hoi_learning/objects/your_object

# Copy files
cp your_object.usd source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
cp your_object_data/surface.npy source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
cp your_object_data/sdf_128.npz source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
```

### Step 5: Register Object

Edit `source/g1_hoi_learning/g1_hoi_learning/objects/__init__.py`:
```python
YOUR_OBJECT_USD_PATH = f"{ASSET_DIR}/your_object/your_object.usd"
```

Edit `source/g1_hoi_learning/g1_hoi_learning/objects/object_cfg.py`:
```python
from g1_hoi_learning.objects import YOUR_OBJECT_USD_PATH

YOUR_OBJECT_CFG = _object_cfg(YOUR_OBJECT_USD_PATH)

OBJECT_CFG_BY_NAME = {
    # ... existing objects ...
    "your_object": YOUR_OBJECT_CFG,
}
```

## 🛠️ Available Scripts

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `convert_mesh_to_usd.py` | Convert STL/OBJ to USD | .stl/.obj | .usd |
| `generate_object_data.py` | Generate surface & SDF | .stl/.obj | .npy, .npz |
| `validate_object_data.py` | Validate & visualize | data dir | report |

## 📊 Data Format

### surface.npy
```python
Shape:  (512, 3)      # 512 surface points, xyz coordinates
Dtype:  float32       # Float32
Units:  meters (m)    # Same as USD
```

### sdf_128.npz
```python
Required fields:
  'sdf':        (128, 128, 128) float32  # SDF grid
  'center':     (3,) float32             # Object center
  'radius':     () float32               # Bounding radius
  'grid_bound': () float32               # Grid bound (1.25)
  'resolution': () int32                 # Resolution (128)
  'object_name': () str                  # Object name
```

## ⚡ One-Line Setup

```bash
# Complete pipeline (assuming mm units)
OBJ=chair SCALE=0.001 && \
python scripts/convert_mesh_to_usd.py --input ${OBJ}.stl --output ${OBJ}.usd --scale $SCALE && \
python -c "import trimesh; m=trimesh.load('${OBJ}.stl'); m.apply_scale($SCALE); m.export('${OBJ}_scaled.stl')" && \
python scripts/generate_object_data.py --mesh ${OBJ}_scaled.stl --output ./${OBJ}_data --name $OBJ && \
python scripts/validate_object_data.py --object $OBJ --objects-dir ./${OBJ}_data
```

## 🔍 Validation Checklist

- [ ] USD opens in Isaac Sim
- [ ] Object size is reasonable (0.5m-2m)
- [ ] Collision shape exists
- [ ] surface.npy shape is (512, 3)
- [ ] sdf_128.npz shape is (128, 128, 128)
- [ ] Registered in `__init__.py` and `object_cfg.py`
- [ ] Same scale used for all files

## 🆘 Common Issues

**USD file too large/small**
- Solution: Regenerate with correct `--scale` parameter

**SDF generation fails**
- Check: Is mesh watertight?
- Solution: Fix mesh in MeshLab (Filters → Cleaning → Close Holes)

**Collision not working**
- Check: Does USD have Collision Shape?
- Solution: Re-export with `--no-collision` flag removed

**Surface sampling uneven**
- Solution: Increase sample count: `--num-surface-samples 1024`

## 📚 Documentation

- **Chinese Quick Start**: `docs/QUICKSTART_zh.md`
- **STL to USD Guide**: `docs/stl_to_usd_guide_zh.md`
- **Data Preparation Guide**: `docs/prepare_object_data_zh.md`
- **Tools README**: `docs/object_data_tools_README.md`
- **Full Index**: `docs/INDEX_zh.md`

## 🔧 Installation

```bash
# Core dependencies
pip install trimesh mesh-to-sdf matplotlib

# Optional (for USD generation)
pip install usd-core
# OR use Isaac Sim's Python
```

## 💡 Tips

1. Test with a simple cube first
2. Always use the same scale for USD and data
3. Verify each step with validation script
4. Reference existing objects (e.g., woodchair)
5. Keep original STL files for adjustments

## 📞 Need Help?

1. Check existing examples: `objects/woodchair/`
2. Run validation script for diagnostics
3. Read detailed guides in `docs/`
4. Check script output for error messages

Happy object preparation! 🎉
