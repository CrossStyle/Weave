#!/usr/bin/env python3
"""
Analyze joint effort data by anatomical body parts.

Usage:
    python analyze_effort_by_body_part.py <path_to_joint_effort_analysis.json>

Example:
    python analyze_effort_by_body_part.py logs/rsl_rl/experiment/run/eval/joint_effort_analysis.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


# Define anatomical groupings based on joint name patterns
BODY_PART_PATTERNS = {
    "Hip": ["hip_yaw", "hip_roll", "hip_pitch"],
    "Knee": ["knee"],
    "Ankle": ["ankle_pitch", "ankle_roll"],
    "Waist": ["waist_roll", "waist_pitch", "waist_yaw"],
    "Shoulder": ["shoulder_pitch", "shoulder_roll", "shoulder_yaw"],
    "Elbow": ["elbow"],
    "Wrist": ["wrist_roll", "wrist_pitch", "wrist_yaw"],
    "Thumb": ["thumb_proximal", "thumb_intermediate", "thumb_distal"],
    "Index Finger": ["index_proximal", "index_intermediate"],
    "Middle Finger": ["middle_proximal", "middle_intermediate"],
    "Ring Finger": ["ring_proximal", "ring_intermediate"],
    "Pinky Finger": ["pinky_proximal", "pinky_intermediate"],
}


def classify_joint(joint_name: str) -> str:
    """Classify a joint into an anatomical body part."""
    joint_lower = joint_name.lower()
    for body_part, patterns in BODY_PART_PATTERNS.items():
        for pattern in patterns:
            if pattern in joint_lower:
                return body_part
    return "Other"


def group_by_limit_and_body_part(joint_analysis: list) -> dict:
    """Group joints by body part and effort limit."""
    # Structure: {body_part: {limit: [joint_data, ...]}}
    groups = defaultdict(lambda: defaultdict(list))
    
    for joint in joint_analysis:
        body_part = classify_joint(joint["joint_name"])
        limit = joint["effort_limit"]
        groups[body_part][limit].append(joint)
    
    return groups


def compute_group_stats(joints: list) -> dict:
    """Compute aggregated statistics for a group of joints."""
    if not joints:
        return {}
    
    # Use the first joint's limit as they should all be the same
    limit = joints[0]["effort_limit"]
    
    # Aggregate statistics
    total_mean = sum(j["mean_effort"] for j in joints) / len(joints)
    max_of_max = max(j["max_effort"] for j in joints)
    avg_margin = limit - total_mean
    peak_ratio = max_of_max / limit if limit > 0 else 0.0
    margin_pct = (avg_margin / limit * 100) if limit > 0 else 0.0
    
    return {
        "num_joints": len(joints),
        "joint_names": [j["joint_name"] for j in joints],
        "limit": limit,
        "mean_effort": total_mean,
        "max_effort": max_of_max,
        "margin": avg_margin,
        "peak_ratio": peak_ratio,
        "margin_percentage": margin_pct,
    }


def print_analysis(groups: dict):
    """Print formatted analysis by body part."""
    print("\n" + "=" * 100)
    print("JOINT EFFORT ANALYSIS BY ANATOMICAL BODY PART")
    print("=" * 100)
    print(f"\n{'Body Part':<20} {'Limit':>8} {'Mean':>8} {'Max':>8} {'Margin':>8} {'Peak%':>8} {'Margin%':>8} {'Joints':>8}")
    print("-" * 100)
    
    # Sort by body part name for consistent output
    for body_part in sorted(groups.keys()):
        limit_groups = groups[body_part]
        
        # Sort by limit value
        for limit in sorted(limit_groups.keys()):
            stats = compute_group_stats(limit_groups[limit])
            
            if not stats:
                continue
            
            # Create body part label with limit if multiple groups
            if len(limit_groups) > 1:
                label = f"{body_part} ({limit:.0f}N·m)"
            else:
                label = body_part
            
            print(f"{label:<20} "
                  f"{stats['limit']:>8.1f} "
                  f"{stats['mean_effort']:>8.2f} "
                  f"{stats['max_effort']:>8.2f} "
                  f"{stats['margin']:>8.2f} "
                  f"{stats['peak_ratio']*100:>7.1f}% "
                  f"{stats['margin_percentage']:>7.1f}% "
                  f"{stats['num_joints']:>8}")
    
    print("-" * 100)
    
    # Highlight high utilization body parts
    print("\n⚠️  HIGH UTILIZATION BODY PARTS (Peak > 80%):")
    high_util = []
    for body_part, limit_groups in groups.items():
        for limit, joints in limit_groups.items():
            stats = compute_group_stats(joints)
            if stats and stats['peak_ratio'] > 0.8:
                high_util.append((body_part, stats))
    
    if high_util:
        for body_part, stats in sorted(high_util, key=lambda x: -x[1]['peak_ratio']):
            print(f"  - {body_part}: {stats['peak_ratio']*100:.1f}% "
                  f"({stats['max_effort']:.2f}/{stats['limit']:.1f} N·m, "
                  f"{stats['num_joints']} joints)")
    else:
        print("  None")
    
    # Show detailed joint composition for each body part
    print("\n" + "=" * 100)
    print("DETAILED JOINT COMPOSITION BY BODY PART")
    print("=" * 100)
    for body_part in sorted(groups.keys()):
        limit_groups = groups[body_part]
        for limit in sorted(limit_groups.keys()):
            stats = compute_group_stats(limit_groups[limit])
            if not stats:
                continue
            
            if len(limit_groups) > 1:
                label = f"{body_part} (Limit: {limit:.0f} N·m)"
            else:
                label = body_part
            
            print(f"\n{label}:")
            print(f"  Joints ({stats['num_joints']}): {', '.join(stats['joint_names'])}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    json_file = Path(sys.argv[1])
    
    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        sys.exit(1)
    
    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    if "warning" in data:
        print(f"Warning: {data['warning']}")
        return
    
    if "joint_analysis" not in data:
        print("Error: Invalid JSON format. Missing 'joint_analysis' field.")
        sys.exit(1)
    
    # Group joints by body part and limit
    groups = group_by_limit_and_body_part(data["joint_analysis"])
    
    # Print analysis
    print_analysis(groups)
    
    # Print overall statistics from original data
    if "overall" in data:
        print("\n" + "=" * 100)
        print("OVERALL STATISTICS")
        print("=" * 100)
        overall = data["overall"]
        print(f"Number of successful environments: {overall['num_success_envs']}")
        print(f"Number of timesteps: {overall['num_timesteps']}")
        print(f"Mean effort (all joints): {overall['mean_effort_all_joints']:.2f} N·m")
        print(f"Max effort (all joints): {overall['max_effort_all_joints']:.2f} N·m")
        print(f"Mean limit: {overall['mean_limit']:.2f} N·m")
    
    print()


if __name__ == "__main__":
    main()
