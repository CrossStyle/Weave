"""
Global object ID registry for consistent object identification across training and evaluation.

This module maintains a fixed mapping from object names to IDs, ensuring that:
1. Training with multiple objects assigns consistent IDs
2. Evaluation/play with a single object uses the same ID as during training
3. Object IDs remain stable across different motion files
"""

# Global object ID registry
# Add your objects here with fixed IDs
OBJECT_ID_REGISTRY = {
    # "clothesstand": 0,
    # "floorlamp": 1,
    # "largebox": 2,
    # "largetable": 3,
    # "smallbox": 4,
    # "smalltable": 5,
    # "tripod": 6,
    # "whitechair": 7,
    "woodchair": 0,
    "h_frame": 1,
    "ladder": 2,
}

# Reverse mapping
ID_TO_OBJECT = {v: k for k, v in OBJECT_ID_REGISTRY.items()}

# Total number of registered objects
NUM_OBJECTS = len(OBJECT_ID_REGISTRY)


def get_object_id(object_name: str) -> int:
    """
    Get the fixed ID for an object name.
    
    Args:
        object_name: Name of the object
    
    Returns:
        Integer ID (0-indexed)
    
    Raises:
        KeyError: If object name not in registry
    """
    if object_name not in OBJECT_ID_REGISTRY:
        raise KeyError(
            f"Object '{object_name}' not found in registry. "
            f"Available objects: {list(OBJECT_ID_REGISTRY.keys())}"
        )
    return OBJECT_ID_REGISTRY[object_name]


def get_object_name(object_id: int) -> str:
    """
    Get the object name for a given ID.
    
    Args:
        object_id: Integer ID
    
    Returns:
        Object name
    
    Raises:
        KeyError: If ID not in registry
    """
    if object_id not in ID_TO_OBJECT:
        raise KeyError(f"Object ID {object_id} not found in registry.")
    return ID_TO_OBJECT[object_id]


def register_objects_from_motion(motion_files: list[str]) -> dict[str, int]:
    """
    Get object IDs for objects in motion files.
    
    Args:
        motion_files: List of motion file paths
    
    Returns:
        Dictionary mapping object names to IDs
    """
    import numpy as np
    
    # Collect unique object names from motion files
    object_names = []
    for f in motion_files:
        data = np.load(f, allow_pickle=True)
        names = [str(x) for x in np.asarray(data["object_names"])]
        for name in names:
            if name not in object_names:
                object_names.append(name)
    
    # Get IDs from registry
    object_id_map = {}
    for name in object_names:
        object_id_map[name] = get_object_id(name)
    
    return object_id_map


def get_num_objects() -> int:
    """Get the total number of registered objects."""
    return NUM_OBJECTS
