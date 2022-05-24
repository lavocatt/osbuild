"""Entrypoints for osbuild

This module contains the application and API entrypoints of `osbuild`, the
command-line-interface to osbuild. The `osbuild_cli()` entrypoint can be safely
used from tests to run the cli.
"""


import argparse
import json
import os
import sys

import osbuild
import osbuild.meta
import osbuild.monitor
from osbuild.objectstore import ObjectStore


RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"


def parse_manifest(path):
    if path == "-":
        manifest = json.load(sys.stdin)
    else:
        with open(path) as f:
            manifest = json.load(f)

    return manifest


def export(name_or_id, output_directory, store, manifest):
    pipeline = manifest[name_or_id]
    obj = store.get(pipeline.id)
    dest = os.path.join(output_directory, name_or_id)

    os.makedirs(dest, exist_ok=True)
    obj.export(dest)


def parse_arguments(sys_argv):
    parser = argparse.ArgumentParser(description="Build operating system images")

    parser.add_argument("manifest_path", metavar="MANIFEST",
                        help="json file containing the manifest that should be built, or a '-' to read from stdin")
    parser.add_argument("--store", metavar="DIRECTORY", type=os.path.abspath,
                        default=".osbuild",
                        help="directory where intermediary os trees are stored")
    parser.add_argument("-l", "--libdir", metavar="DIRECTORY", type=os.path.abspath, default="/usr/lib/osbuild",
                        help="the directory containing stages, assemblers, and the osbuild library")
    parser.add_argument("--checkpoint", metavar="ID", action="append", type=str, default=None,
                        help="stage to commit to the object store during build (can be passed multiple times)")
    parser.add_argument("--export", metavar="ID", action="append", type=str, default=[],
                        help="object to export, can be passed multiple times")
    parser.add_argument("--output-directory", metavar="DIRECTORY", type=os.path.abspath,
                        help="directory where result objects are stored")
    parser.add_argument("--inspect", action="store_true",
                        help="return the manifest in JSON format including all the ids")
    parser.add_argument("--monitor", metavar="NAME", default=None,
                        help="Name of the monitor to be used")
    parser.add_argument("--monitor-fd", metavar="FD", type=int, default=sys.stdout.fileno(),
                        help="File descriptor to be used for the monitor")
    parser.add_argument("--stage-timeout", type=int, default=None,
                        help="set the maximal time (in seconds) each stage is allowed to run")
    parser.add_argument("--json", action="store_true", help="output results in JSON format")
    parser.add_argument("--result-format", type=str, default="legacy", choices=["legacy"],
                        help="choose between output formats")

    return parser.parse_args(sys_argv[1:])


def parse_result_format(is_json, res_fmt):
    suffix = "text"
    if is_json:
        suffix = "json"
    return f"{res_fmt}_{suffix}"

# pylint: disable=too-many-branches,too-many-return-statements,too-many-statements


def osbuild_cli():
    args = parse_arguments(sys.argv)
    desc = parse_manifest(args.manifest_path)

    index = osbuild.meta.Index(args.libdir)

    # detect the format from the manifest description
    info = index.detect_format_info(desc)
    if not info:
        print("Unsupported manifest format")
        return 2
    if "IN" not in info.format_kind:
        print("Manifest format can't parse input manifest")
        return 2
    mfst_fmt = info.module

    # detect the result format
    rslt_fmt = index.get_result_fmt(info, parse_result_format(args.json, args.result_format))
    if not rslt_fmt:
        print("Unsupported result format")
        return 2

    # first thing is validation of the manifest
    res = mfst_fmt.validate(desc, index)
    if not res:
        if args.inspect:
            rslt_fmt.inspect(res)
        else:
            rslt_fmt.print_validation_result(res, args.manifest_path)
        return 2

    manifest = mfst_fmt.load(desc, index)

    exports = set(args.export)
    unresolved = [e for e in exports if e not in manifest]
    if unresolved:
        rslt_fmt.print_export_error(unresolved, args.json)
        return 1

    if args.checkpoint:
        missed = manifest.mark_checkpoints(args.checkpoint)
        if missed:
            rslt_fmt.print_checkpoint_error(missed, args.json)
            return 1

    if args.inspect:
        rslt_fmt.print_description(mfst_fmt.describe(manifest, with_id=True))
        return 0

    output_directory = args.output_directory

    if exports and not output_directory:
        rslt_fmt.print_export_config_error(args.json)
        return 1

    monitor_name = args.monitor
    if not monitor_name:
        monitor_name = "NullMonitor" if args.json else "LogMonitor"
    monitor = osbuild.monitor.make(monitor_name, args.monitor_fd)

    try:
        with ObjectStore(args.store) as object_store:
            stage_timeout = args.stage_timeout

            pipelines = manifest.depsolve(object_store, exports)

            manifest.download(object_store, monitor, args.libdir)

            r = manifest.build(
                object_store,
                pipelines,
                monitor,
                args.libdir,
                stage_timeout=stage_timeout
            )

            if r["success"] and exports:
                for pid in exports:
                    export(pid, output_directory, object_store, manifest)

    except KeyboardInterrupt:
        rslt_fmt.print_aborted_error(args.json)
        return 130

    rslt_fmt.print_result(manifest, r, info)
    return 0 if r["success"] else 1
