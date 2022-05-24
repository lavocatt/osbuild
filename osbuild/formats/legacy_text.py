"""Text formatting for output

Will output mostly text
"""
import json
import sys
from typing import Dict
from ..pipeline import Manifest

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"

FORMAT_KIND = ["OUT"]
VERSION = "legacy_text"
COMPATIBLE_RESULT_FORMATS = None


def _print_text_error(error: str):
    print(f"{RESET}{BOLD}{RED}{error}{RESET}")


def print_result(manifest: Manifest, res: Dict, _info) -> Dict:
    if res["success"]:
        for name, pl in manifest.pipelines.items():
            print(f"{name + ':': <10}\t{pl.id}")
    print()
    _print_text_error("failed")


def print_inspection(result, _name):
    json.dump(result.as_dict(), sys.stdout, indent=2)  # pretty print the JSON


def print_validation_result(result, name):
    if name == "-":
        name = "<stdin>"

    print(f"{BOLD}{name}{RESET} ", end='')

    if result:
        print(f"is {BOLD}{GREEN}valid{RESET}")
        return

    print(f"has {BOLD}{RED}errors{RESET}:")
    print("")

    for error in result:
        print(f"{BOLD}{error.id}{RESET}:")
        print(f"  {error.message}\n")


def print_export_error(unresolved):
    for name in unresolved:
        print(f"Export {BOLD}{name}{RESET} not found!")
    _print_text_error("Failed")


def print_checkpoint_error(missed):
    for checkpoint in missed:
        print(f"Checkpoint {BOLD}{checkpoint}{RESET} not found!")
    _print_text_error("Failed")


def print_description(description):
    json.dump(description, sys.stdout, indent=2)  # pretty print the JSON


def print_export_config_error():
    _print_text_error("Need --output-directory for --export")


def print_aborted_error():
    print()
    _print_text_error("Aborted")
