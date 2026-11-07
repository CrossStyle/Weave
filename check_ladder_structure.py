"""Check ladder USD structure to understand the contact sensor issue."""
from pxr import Usd, UsdGeom, UsdPhysics
import sys

usd_files = [
    "source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_collision.usd",
    "source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_support1.usd",
]

for usd_path in usd_files:
    print("=" * 80)
    print(f"Analyzing: {usd_path}")
    print("=" * 80)
    
    try:
        stage = Usd.Stage.Open(usd_path)
        if not stage:
            print(f"ERROR: Could not open {usd_path}")
            continue
        
        # Get all prims
        print("\nPrim hierarchy:")
        for prim in stage.Traverse():
            indent = "  " * (len(prim.GetPath().pathString.split('/')) - 2)
            prim_type = prim.GetTypeName()
            print(f"{indent}{prim.GetPath()} [{prim_type}]")
            
            # Check if it has collision
            if UsdPhysics.CollisionAPI(prim):
                print(f"{indent}  -> Has CollisionAPI")
            
            # Check if it's a rigid body
            if UsdPhysics.RigidBodyAPI(prim):
                print(f"{indent}  -> Has RigidBodyAPI")
        
        # Count rigid bodies
        rigid_bodies = [p for p in stage.Traverse() if UsdPhysics.RigidBodyAPI(p)]
        print(f"\nTotal rigid bodies: {len(rigid_bodies)}")
        
        # Count collision meshes
        collision_prims = [p for p in stage.Traverse() if UsdPhysics.CollisionAPI(p)]
        print(f"Total collision prims: {len(collision_prims)}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
