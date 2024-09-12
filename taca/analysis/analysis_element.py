"""Analysis methods for sequencing runs produced by Element instruments."""

import glob
import logging
import os

from taca.element.Aviti_Runs import Aviti_Run
from taca.utils.config import CONFIG

logger = logging.getLogger(__name__)


def run_preprocessing(given_run):
    """Run demultiplexing in all data directories.

    :param str given_run: Process a particular run instead of looking for runs
    """

    def _process(run):
        """Process a run/flowcell and transfer to analysis server.

        :param taca.element.Run run: Run to be processed and transferred
        """
        run.parse_run_parameters()
        sequencing_done = run.check_sequencing_status()
        demultiplexing_status = run.get_demultiplexing_status()
        if not sequencing_done:  # Sequencing ongoing
            current_run_status = "sequencing"
            if run.status_changed(current_run_status):
                run.update_statusdb()
        elif (
            sequencing_done and demultiplexing_status == "not started"
        ):  # Sequencing done. Start demux
            if (
                not run.manifest_exists()
            ):  # TODO: this should check for the zip file in lims output location
                logger.warn(f"Run manifest is missing for {run}")
                # TODO: email operator warning
                return
            elif run.manifest_exists():
                os.mkdir(run.demux_dir)
                run.copy_manifests()
                run_manifests = glob.glob(
                    os.path.join(run.run_dir, "RunManifest_*.csv")
                )  # TODO: is this filename right?
                sub_demux_count = 0
                for run_manifest in run_manifests.sort():
                    if len(run_manifests) == 1:
                        demux_dir = run.demux_dir
                    elif len(run_manifests) > 1:
                        demux_dir = f"Demultiplexing_{sub_demux_count}"
                    os.mkdir(demux_dir)
                    run.start_demux(run_manifest, demux_dir)
                    sub_demux_count += 1
                current_run_status = "demultiplexing"
                if run.status_changed(current_run_status):
                    run.update_statusdb(current_run_status)
        elif sequencing_done and demultiplexing_status == "ongoing":
            current_run_status = "demultiplexing"
            if run.status_changed(current_run_status):
                run.update_statusdb(current_run_status)
            return
        elif sequencing_done and demultiplexing_status == "finished":
            transfer_file = CONFIG.get("Element").get("Aviti").get("transfer_log")
            if not run.is_transferred(transfer_file) and not run.transfer_ongoing():
                # TODO: if multiple demux dirs, aggregate the results into Demultiplexing?
                run.aggregate_demux_results
                run.sync_metadata()
                run.make_transfer_indicator()
                current_run_status = "transferring"
                if run.status_changed(current_run_status):
                    run.update_statusdb(current_run_status)
                    # TODO: Also update statusdb with a timestamp of when the transfer started
                run.transfer()
                run.remove_transfer_indicator()
                run.update_transfer_log(transfer_file)
                current_run_status = "transferred"
                if run.status_changed(current_run_status):
                    run.update_statusdb(current_run_status)
                run.archive()
                current_run_status = "archived"
                if run.status_changed(current_run_status):
                    run.update_statusdb(current_run_status)
            elif not run.is_transferred(transfer_file) and run.transfer_ongoing():
                current_run_status = "transferring"
                if run.status_changed(current_run_status):
                    run.update_statusdb(current_run_status)
                logger.info(f"{run} is being transferred. Skipping.")
                return
            elif run.is_transferred(transfer_file):
                logger.warn(
                    f"The run {run.flowcell_id} has already been transferred but has not been archived. Please investigate"
                )
                # TODO: email operator warning
                return
            else:
                logger.warn(
                    f"Unknown transfer status of run {run.flowcell_id}. Please investigate"
                )

    if given_run:
        run = Aviti_Run(given_run)
        # TODO: Needs to change if more types of Element machines are aquired in the future

        _process(run)
    else:
        data_dirs = CONFIG.get("element_analysis").get(
            "data_dirs"
        )  # TODO: add to config
        for data_dir in data_dirs:  # TODO: make sure to look in both side A and B
            # Run folder looks like DATE_*_*_*, the last section is the FC name.
            runs = glob.glob(
                os.path.join(data_dir, "[1-9]*_*_*_*")
            )  # TODO: adapt to aviti format
            for run in runs:
                runObj = Aviti_Run(run)
                try:
                    _process(runObj)
                except:  # TODO: chatch error message and print it
                    # This function might throw and exception,
                    # it is better to continue processing other runs
                    logger.warning(f"There was an error processing the run {run}")
                    # TODO: Think about how to avoid silent errors (email?)
                    pass
