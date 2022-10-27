# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from bugmon import BugMonitor
from bugmon.bug import EnhancedBug
from bugmon.utils import get_pernosco_trace

from ..common import fetch_artifact, in_taskcluster, BugmonTaskError, queue
from ..common.cli import base_parser

LOG = logging.getLogger(__name__)


def process_bug(bug_data, proc_dest, trace_dest=None, force_confirm=False):
    bug = EnhancedBug(bugsy=None, **bug_data)

    with tempfile.TemporaryDirectory() as temp_dir:
        working_path = Path(temp_dir)
        bugmon = BugMonitor(
            None,
            bug,
            working_path,
            dry_run=True,
        )

        LOG.info(f"Processing bug {bug.id} (Status: {bug.status})")
        bugmon.process(force_confirm)

        with open(proc_dest, "w") as file:
            json.dump({"bug_number": bug.id, "diff": bug.diff()}, file, indent=2)

        if trace_dest is not None:
            latest_trace = get_pernosco_trace(bugmon.log_dir)

            if latest_trace is None:
                raise BugmonTaskError("Unable to identify a pernosco trace!")

            LOG.info(f"Found pernosco trace at {latest_trace}")
            LOG.info("Compressing rr trace (this may take a while)...")
            shutil.make_archive(
                # Assumes arg.trace_artifact with a suffix of ".tar.gz"
                base_name=trace_dest.with_suffix("").with_suffix(""),
                format="gztar",
                root_dir=str(latest_trace),
            )

        return None


def parse_args(argv):
    """Parse arguments"""
    parser = base_parser(prog="BugmonProcessor")
    parser.add_argument(
        "monitor_artifact",
        type=Path,
        help="Path to monitor artifact",
    )
    parser.add_argument(
        "processor_artifact",
        type=Path,
        help="Path to store the processor artifact",
    )
    parser.add_argument(
        "--trace-artifact",
        type=Path,
        help="Path to store the rr trace archive.",
    )
    parser.add_argument(
        "--force-confirm",
        action="store_true",
        help="Force bug confirmation regardless of state",
        default=os.environ.get("FORCE_CONFIRM", None),
    )

    args = parser.parse_args(args=argv)
    logging.basicConfig(level=args.log_level)

    if args.processor_artifact.exists():
        LOG.warning(
            f"Path {args.processor_artifact} exists! Contents will be overwritten!"
        )

    if args.trace_artifact and args.trace_artifact.exists():
        LOG.warning(f"Path {args.trace_artifact} exists! Contents will be overwritten!")

    return args


def main(argv=None):
    """Process bug"""
    args = parse_args(argv)

    if in_taskcluster():
        task = queue.task(os.getenv("TASK_ID"))
        task_id = task.get("taskGroupId")
        monitor_artifact = fetch_artifact(task_id, args.monitor_artifact)
    else:
        monitor_artifact = json.loads(args.monitor_artifact.read_text())

    process_bug(
        monitor_artifact,
        args.processor_artifact,
        trace_dest=args.trace_artifact,
        force_confirm=args.force_confirm,
    )
