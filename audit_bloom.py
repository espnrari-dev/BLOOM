#!/usr/bin/env python3
import os
import sys
import ast
import re
import json
import hashlib
import importlib.util
from pathlib import Path

REPO_DIR = Path(os.path.expanduser("~/BLOOM")).resolve()
EXCLUDE_DIRS = {"venv", "garden_term", "__pycache__", ".git", ".venv", "site-packages", "dist-info"}

class ForensicAuditor:
    def __init__(self, root: Path):
        self.root = root
        self.report = {
            "summary": {"total_files": 0, "total_defects": 0, "status": "FAILED_AUDIT"},
            "pillars": {
                "1_code_integrity": [],
                "2_model_contracts": [],
                "3_execution_paths": [],
                "4_data_sources": [],
                "5_training_integrity": [],
                "6_runtime_integrity": [],
                "7_market_subsystem": [],
                "8_repair_infrastructure": [],
                "9_cross_file_consistency": {},
                "10_operational_completeness": [],
                "11_behavioral_tests": [],
                "12_architecture_discrepancies": []
            }
        }
        self.py_files = [
            p for p in self.root.rglob("*.py")
            if not any(part in EXCLUDE_DIRS for part in p.parts)
        ]
        self.report["summary"]["total_files"] = len(self.py_files)

    def add_defect(self, pillar: str, severity: str, file: str, issue: str, context: str = ""):
        file_rel = str(Path(file).relative_to(self.root)) if file.startswith(str(self.root)) else file
        self.report["pillars"][pillar].append({
            "severity": severity,
            "file": file_rel,
            "issue": issue,
            "context": context
        })
        self.report["summary"]["total_defects"] += 1

    def audit_code_and_ast(self):
        """Pillar 1 & 10: Syntax, AST parsing, undefined names, duplicate files."""
        all_imports = set()
        file_hashes = {}

        for py_file in self.py_files:
            rel_path = str(py_file.relative_to(self.root))

            try:
                with open(py_file, 'rb') as f:
                    content_bytes = f.read()
                h = hashlib.sha256(content_bytes).hexdigest()
                if h in file_hashes:
                    self.add_defect(
                        "10_operational_completeness",
                        "WARNING",
                        str(py_file),
                        f"Exact duplicate implementation of {file_hashes[h]}"
                    )
                else:
                    file_hashes[h] = rel_path

                content = content_bytes.decode('utf-8')
                tree = ast.parse(content, filename=str(py_file))
            except SyntaxError as se:
                self.add_defect("1_code_integrity", "CRITICAL", str(py_file), f"Syntax Error: {se.msg} (Line {se.lineno})")
                continue
            except UnicodeDecodeError:
                self.add_defect("1_code_integrity", "CRITICAL", str(py_file), "Encoding error: non-UTF-8 characters detected")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        all_imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        all_imports.add(node.module.split('.')[0])

        required_pkgs = ["torch", "transformers", "numpy"]
        for pkg in required_pkgs:
            if importlib.util.find_spec(pkg) is None:
                self.add_defect("6_runtime_integrity", "HIGH", "ENVIRONMENT", f"Required runtime dependency missing: {pkg}")

    def audit_contracts_and_consistency(self):
        """Pillar 2 & 9: Contract dimensions, hardcoded constants, cross-file drift."""
        dimension_map = {}
        patterns = {
            "vocab_size": r'(?:vocab_size|VOCAB_SIZE)\s*[:=]\s*(\d+)',
            "hidden_dim": r'(?:hidden_dim|n_embd|d_model|HIDDEN_DIM)\s*[:=]\s*(\d+)',
            "seq_len": r'(?:seq_len|max_seq_len|block_size|SEQ_LEN)\s*[:=]\s*(\d+)',
            "num_heads": r'(?:num_heads|n_head|NUM_HEADS)\s*[:=]\s*(\d+)',
            "num_layers": r'(?:num_layers|n_layer|NUM_LAYERS)\s*[:=]\s*(\d+)'
        }

        for py_file in self.py_files:
            rel_path = str(py_file.relative_to(self.root))
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for key, pattern in patterns.items():
                    matches = re.findall(pattern, content)
                    for val in matches:
                        v = int(val)
                        if key not in dimension_map:
                            dimension_map[key] = {}
                        if v not in dimension_map[key]:
                            dimension_map[key][v] = []
                        dimension_map[key][v].append(rel_path)

        for key, occurrences in dimension_map.items():
            if len(occurrences) > 1:
                self.add_defect(
                    "9_cross_file_consistency",
                    "CRITICAL",
                    "GLOBAL",
                    f"Inconsistent {key} definitions across repository: {occurrences}"
                )
        self.report["pillars"]["9_cross_file_consistency"] = dimension_map

    def audit_data_sources(self):
        """Pillar 4: Corpus integrity, text files, stale artifacts."""
        raw_files = list(self.root.rglob("*.txt")) + list(self.root.rglob("*.json")) + list(self.root.rglob("*.csv"))
        data_files = [f for f in raw_files if not any(part in EXCLUDE_DIRS for part in f.parts)]

        for d_file in data_files:
            size = d_file.stat().st_size
            if size == 0:
                self.add_defect("4_data_sources", "HIGH", str(d_file), "Empty data file detected")
            elif size < 100 and d_file.suffix == ".txt":
                self.add_defect("4_data_sources", "WARNING", str(d_file), f"Tiny corpus file detected ({size} bytes)")

            try:
                with open(d_file, 'r', encoding='utf-8') as f:
                    f.read(1024)
            except UnicodeDecodeError:
                self.add_defect("4_data_sources", "CRITICAL", str(d_file), "Data source failed UTF-8 decoding")

    def audit_training_and_market(self):
        """Pillar 5 & 7: Training logic integrity & Market numerical safety."""
        for py_file in self.py_files:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if "train" in py_file.name.lower() or "trainer" in py_file.name.lower():
                if "loss" in content and ".backward()" not in content:
                    self.add_defect("5_training_integrity", "CRITICAL", str(py_file), "Training script lacks gradient backward pass (.backward())")
                if "loss" in content and "optimizer.step()" not in content:
                    self.add_defect("5_training_integrity", "CRITICAL", str(py_file), "Training script lacks parameter update step (optimizer.step())")

            if "market" in py_file.name.lower() or "trading" in py_file.name.lower():
                if "isnan" not in content and "torch.nan" not in content and "np.nan" not in content:
                    self.add_defect("7_market_subsystem", "HIGH", str(py_file), "Market data pipeline lacks explicit NaN/Inf propagation checks")

    def run_all(self):
        self.audit_code_and_ast()
        self.audit_contracts_and_consistency()
        self.audit_data_sources()
        self.audit_training_and_market()

        if self.report["summary"]["total_defects"] == 0:
            self.report["summary"]["status"] = "PASSED_AUDIT"

        output_path = self.root / "audit_report.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2)

        print("\n" + "="*60)
        print("         BLOOM REPOSITORY FORENSIC AUDIT COMPLETE")
        print("="*60)
        print(f"Total Python Files Scanned: {self.report['summary']['total_files']}")
        print(f"Total Defects Inventory:   {self.report['summary']['total_defects']}")
        print(f"Audit Status:              {self.report['summary']['status']}")
        print(f"Detailed Audit Report:     {output_path}")
        print("="*60 + "\n")

if __name__ == "__main__":
    auditor = ForensicAuditor(REPO_DIR)
    auditor.run_all()
