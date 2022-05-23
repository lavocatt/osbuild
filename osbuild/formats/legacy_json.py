"""Legacy JSON formatting for output

Will output mostly json
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
VERSION = "legacy_json"
COMPATIBLE_RESULT_FORMATS = None

#pylint: disable=too-many-branches


def output_v2(manifest: Manifest, res: Dict) -> Dict:
    """Convert a result into the v2 format"""

    if not res["success"]:
        last = list(res.keys())[-1]
        failed = res[last]["stages"][-1]

        result = {
            "type": "error",
            "success": False,
            "error": {
                "type": "org.osbuild.error.stage",
                "details": {
                    "stage": {
                        "id": failed["id"],
                        "type": failed["name"],
                        "output": failed["output"],
                        "error": failed["error"]
                    }
                }
            }
        }
    else:
        result = {
            "type": "result",
            "success": True,
            "metadata": {}
        }

        # gather all the metadata
        for p in manifest.pipelines.values():
            data = {}
            r = res.get(p.id, {})
            for stage in r.get("stages", []):
                md = stage.get("metadata")
                if not md:
                    continue
                name = stage["name"]
                val = data.setdefault(name, {})
                val.update(md)

            if data:
                result["metadata"][p.name] = data

    # generate the log
    result["log"] = {}
    for p in manifest.pipelines.values():
        r = res.get(p.id, {})
        log = []

        for stage in r.get("stages", []):
            data = {
                "id": stage["id"],
                "type": stage["name"],
                "output": stage["output"]
            }
            if not stage["success"]:
                data["success"] = stage["success"]
                if stage["error"]:
                    data["error"] = stage["error"]

            log.append(data)

        if log:
            result["log"][p.name] = log

    return result


def output_v1(manifest: Manifest, res: Dict) -> Dict:
    """Convert a result into the v1 format"""

    def result_for_pipeline(pipeline):
        # The pipeline might not have been built one of its
        # dependencies, i.e. its build pipeline, failed to
        # build. We thus need to be tolerant of a missing
        # result but still need to to recurse
        current = res.get(pipeline.id, {})
        retval = {
            "success": current.get("success", True)
        }

        if pipeline.build:
            build = manifest[pipeline.build]
            retval["build"] = result_for_pipeline(build)
            retval["success"] = retval["build"]["success"]

        stages = current.get("stages")
        if stages:
            retval["stages"] = stages
        return retval

    result = result_for_pipeline(manifest["tree"])

    assembler = manifest.get("assembler")
    if not assembler:
        return result

    current = res.get(assembler.id)
    # if there was an error before getting to the assembler
    # pipeline, there might not be a result present
    if not current:
        return result

    result["assembler"] = current["stages"][0]
    if not result["assembler"]["success"]:
        result["success"] = False

    return result


def output(manifest: Manifest, res: Dict, info) -> Dict:
    if info.version == "1":
        return output_v1(manifest, res)
    return output_v2(manifest, res)


def print_text_error(error: str):
    print(f"{RESET}{BOLD}{RED}{error}{RESET}")


def print_result(manifest: Manifest, res: Dict, info) -> Dict:
    json.dump(output(manifest, res, info), sys.stdout)
    sys.stdout.write("\n")


def inspect(result, _name):
    json.dump(result.as_dict(), sys.stdout)
    sys.stdout.write("\n")


def print_validation_result(result, name):
    return inspect(result, name)


def print_export_error(unresolved):
    # /!\ In legacy.py, there's a mix of text and json output
    for name in unresolved:
        print(f"Export {BOLD}{name}{RESET} not found!")
    print_text_error("Failed")


def print_checkpoint_error(missed):
    # /!\ In legacy.py, there's a mix of text and json output
    for checkpoint in missed:
        print(f"Checkpoint {BOLD}{checkpoint}{RESET} not found!")
    print_text_error("Failed")


def print_description(description):
    json.dump(description, sys.stdout)
    sys.stdout.write("\n")


def print_export_config_error():
    # /!\ In legacy.py, there's a mix of text and json output
    print_text_error("Need --output-directory for --export")


def print_aborted_error():
    # /!\ In legacy.py, there's a mix of text and json output
    print()
    print_text_error("Aborted")
