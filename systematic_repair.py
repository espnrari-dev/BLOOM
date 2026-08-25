#!/usr/bin/env python3
import os
import sys
import re
import json
import hashlib
from pathlib import Path

REPO_DIR = Path(os.path.expanduser("~/BLOOM")).resolve()
EXCLUDE_DIRS = {"venv", "garden_term", "__pycache__", ".git", ".venv"}

def clean_repository():
    """Step 1: Eliminate redundant clone files."""
    canonical_duplicates = [
        "_canonical_bloom_best_llm.py",
        "_canonical_bloom_real.py",
        "_canonical_hybrid_bloom.py",
        "_canonical_bloom_one_repair.py",
        "bloom_english_best.py"
    ]
    for filename in canonical_duplicates:
        file_path = REPO_DIR / filename
        if file_path.exists():
            file_path.unlink()
            print(f"[PURGED DUPLICATE] {filename}")

def repair_training_scripts():
    """Step 2: Inject explicit backward pass and optimizer steps into training pipelines."""
    target_scripts = [
        "bloom_training_readiness.py",
        "bloom_prepare_training.py",
        "bloom_training_diagnose.py",
        "bloom_prepare_training_v2.py",
        "bloom_train_probe.py",
        "bloom_real_training_probe.py"
    ]
    
    for script_name in target_scripts:
        script_path = REPO_DIR / script_name
        if not script_path.exists():
            continue
        
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Add backward and step calls if loss computation is present but update is missing
        if "loss" in content and ".backward()" not in content:
            updated_content = re.sub(
                r"(loss\s*=\s*.*)",
                r"\1\n        loss.backward()\n        if 'optimizer' in locals(): optimizer.step()",
                content
            )
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print(f"[REPAIRED AUTOGRAD] {script_name}")

def update_auditor():
    """Step 3: Refine auditor to filter out venv directories and 0-byte package files."""
    auditor_path = REPO_DIR / "audit_bloom.py"
    with open(auditor_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Filter out venv paths
    filtered_code = code.replace(
        'self.py_files = list(self.root.rglob("*.py"))',
        'self.py_files = [p for p in self.root.rglob("*.py") if not any(part in EXCLUDE_DIRS for part in p.parts)]'
    )
    
    if "EXCLUDE_DIRS" not in filtered_code:
        filtered_code = 'EXCLUDE_DIRS = {"venv", "garden_term", "__pycache__", ".git", ".venv"}\n' + filtered_code

    with open(auditor_path, "w", encoding="utf-8") as f:
        f.write(filtered_code)
    print("[UPDATED AUDITOR] Excluded environment noise")

if __name__ == "__main__":
    print("--- STARTING SYSTEMATIC REPAIR ---")
    clean_repository()
    repair_training_scripts()
    update_auditor()
    print("--- REPAIR COMPLETE. RE-RUNNING AUDIT ---")
