#!/usr/bin/env python

import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from flowcell_parser.classes import LaneBarcodeParser

from taca.illumina.NextSeq_Runs import NextSeq_Run
from taca.illumina.NovaSeq_Runs import NovaSeq_Run
from taca.illumina.Runs import Run, _create_folder_structure, _generate_lane_html
from taca.illumina.Standard_Runs import Standard_Run
from taca.utils import config as conf

if sys.version_info[0] >= 3:
    unicode = str

# This is only run if TACA is called from the CLI, as this is a test, we need to
# call it explicitely
CONFIG = conf.load_yaml_config("data/taca_test_cfg.yaml")


class TestRuns(unittest.TestCase):
    """Tests for the Run base class."""

    @classmethod
    def setUpClass(self):
        """Creates the following directory tree for testing purposes:

        tmp/
        |__ 141124_ST-COMPLETED_01_AFCIDXX
        |   |__ RunInfo.xml
        |   |__ Demultiplexing
        |   |   |__ Undetermined_S0_L001_R1_001.fastq.gz
        |   |   |__ Stats
        |   |       |__ DemultiplexingStats.xml
        |   |__ RTAComplete.txt
        |   |__ SampleSheet.csv
        |__ 141124_ST-INPROGRESS_02_AFCIDXX
        |   |__ RunInfo.xml
        |   |__ Demultiplexing
        |   |__ Demultiplexing_0
        |   |__ Demultiplexing_1
        |   |__ Demultiplexing_2
        |   |__ Demultiplexing_3
        |   |__ SampleSheet_0.csv
        |   |__ SampleSheet_1.csv
        |   |__ SampleSheet_2.csv
        |   |__ SampleSheet_3.csv
        |   |__ RTAComplete.txt
        |__ 141124_ST-INPROGRESSDONE_02_AFCIDXX
        |   |__ RunInfo.xml
        |   |__ Demultiplexing
        |   |__ Demultiplexing_0
        |   |   |__Stats
        |   |      |__ DemultiplexingStats.xml
        |   |      |__ DemuxSummaryF1L1.txt
        |   |__ Demultiplexing_1
        |   |   |__Stats
        |   |      |__ DemultiplexingStats.xml
        |   |__ Demultiplexing_2
        |   |   |__Stats
        |   |      |__ DemultiplexingStats.xml
        |   |__ Demultiplexing_3
        |   |   |__Stats
        |   |      |__ DemultiplexingStats.xml
        |   |__ SampleSheet_0.csv
        |   |__ SampleSheet_1.csv
        |   |__ SampleSheet_2.csv
        |   |__ SampleSheet_3.csv
        |   |__ RTAComplete.txt
        |__ 141124_ST-RUNNING_03_AFCIDXX
        |   |__ RunInfo.xml
        |__ 141124_ST-TOSTART_04_FCIDXXX
        |   |__ RunInfo.xml
        |   |__ RTAComplete.txt
        |__ 141124_ST-DUMMY1_01_AFCIDXX
        |   |__ RunInfo.xml
        |   |__ SampleSheet.csv
        |__ 141124_ST-COMPLEX1_01_AFCIDXX
        |   |__lots of files
        |__ archive
        """
        self.tmp_dir = os.path.join(tempfile.mkdtemp(), "tmp")
        self.transfer_file = os.path.join(self.tmp_dir, "transfer.tsv")

        running = os.path.join(self.tmp_dir, "141124_ST-RUNNING1_03_AFCIDXX")
        to_start = os.path.join(self.tmp_dir, "141124_ST-TOSTART1_04_FCIDXXX")
        in_progress = os.path.join(self.tmp_dir, "141124_ST-INPROGRESS1_02_AFCIDXX")
        in_progress_done = os.path.join(
            self.tmp_dir, "141124_ST-INPROGRESSDONE1_02_AFCIDXX"
        )
        completed = os.path.join(self.tmp_dir, "141124_ST-COMPLETED1_01_AFCIDXX")
        dummy = os.path.join(self.tmp_dir, "141124_ST-DUMMY1_01_AFCIDXX")
        complex_run_dir = os.path.join(self.tmp_dir, "141124_ST-COMPLEX1_01_AFCIDXX")
        finished_runs = [to_start, in_progress, in_progress_done, completed]

        # Create runs directory structure
        os.makedirs(self.tmp_dir)
        os.makedirs(running)
        os.makedirs(to_start)
        os.makedirs(os.path.join(in_progress, "Demultiplexing"))
        os.makedirs(
            os.path.join(
                in_progress,
                "Demultiplexing_0",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            )
        )
        os.makedirs(os.path.join(in_progress, "Demultiplexing_1"))
        os.makedirs(os.path.join(in_progress, "Demultiplexing_2"))
        os.makedirs(os.path.join(in_progress, "Demultiplexing_3"))
        os.makedirs(os.path.join(in_progress_done, "Demultiplexing"))
        os.makedirs(os.path.join(in_progress_done, "Demultiplexing_0/Stats"))
        os.makedirs(os.path.join(completed, "Demultiplexing", "Stats"))
        os.makedirs(dummy)
        os.makedirs(os.path.join(complex_run_dir, "Demultiplexing"))
        os.makedirs(os.path.join(complex_run_dir, "Demultiplexing_0", "Stats"))
        os.makedirs(os.path.join(complex_run_dir, "Demultiplexing_1", "Stats"))
        os.makedirs(
            os.path.join(
                complex_run_dir,
                "Demultiplexing_0",
                "N__One_20_01",
                "Sample_P12345_1001",
            )
        )
        os.makedirs(
            os.path.join(
                complex_run_dir,
                "Demultiplexing_0",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            )
        )
        os.makedirs(
            os.path.join(
                complex_run_dir,
                "Demultiplexing_1",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            )
        )

        # Create files indicating that the run is finished
        for run in finished_runs:
            open(os.path.join(run, "RTAComplete.txt"), "w").close()

        # Create sample sheets for running demultiplexing
        open(os.path.join(in_progress, "SampleSheet_0.csv"), "w").close()
        open(os.path.join(in_progress, "SampleSheet_1.csv"), "w").close()
        open(os.path.join(in_progress, "SampleSheet_2.csv"), "w").close()
        open(os.path.join(in_progress, "SampleSheet_3.csv"), "w").close()
        open(os.path.join(in_progress_done, "SampleSheet_0.csv"), "w").close()
        shutil.copy("data/samplesheet.csv", os.path.join(completed, "SampleSheet.csv"))
        shutil.copy(
            "data/samplesheet.csv", os.path.join(complex_run_dir, "SampleSheet_0.csv")
        )
        shutil.copy(
            "data/samplesheet.csv", os.path.join(complex_run_dir, "SampleSheet_1.csv")
        )

        # Create files indicating that demultiplexing is ongoing
        open(
            os.path.join(
                in_progress_done, "Demultiplexing_0", "Stats", "DemultiplexingStats.xml"
            ),
            "w",
        ).close()
        open(
            os.path.join(
                in_progress_done, "Demultiplexing_0", "Stats", "DemuxSummaryF1L1.txt"
            ),
            "w",
        ).close()
        shutil.copy(
            "data/lane.html",
            os.path.join(
                in_progress,
                "Demultiplexing_0",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            ),
        )

        # Create files indicating that the preprocessing is done
        open(
            os.path.join(
                completed, "Demultiplexing", "Stats", "DemultiplexingStats.xml"
            ),
            "w",
        ).close()
        open(
            os.path.join(
                completed, "Demultiplexing", "Undetermined_S0_L001_R1_001.fastq.gz"
            ),
            "w",
        ).close()
        open(
            os.path.join(
                complex_run_dir,
                "Demultiplexing_0",
                "N__One_20_01",
                "Sample_P12345_1001",
                "P16510_1001_S1_L001_R1_001.fastq.gz",
            ),
            "w",
        ).close()
        open(
            os.path.join(
                complex_run_dir,
                "Demultiplexing_0",
                "N__One_20_01",
                "Sample_P12345_1001",
                "P16510_1001_S1_L001_R2_001.fastq.gz",
            ),
            "w",
        ).close()
        with open(
            os.path.join(completed, "Demultiplexing", "Stats", "Stats.json"),
            "w",
            encoding="utf-8",
        ) as stats_json:
            stats_json.write(unicode(json.dumps({"silly": 1}, ensure_ascii=False)))

        # Copy transfer file with the completed run
        shutil.copy("data/test_transfer.tsv", self.transfer_file)

        # Move sample RunInfo.xml file to every run directory
        for run in [
            running,
            to_start,
            in_progress,
            in_progress_done,
            completed,
            dummy,
            complex_run_dir,
        ]:
            shutil.copy("data/RunInfo.xml", run)
            shutil.copy("data/runParameters.xml", run)

        # Create files for complex case
        shutil.copy(
            "data/Stats.json",
            os.path.join(complex_run_dir, "Demultiplexing_0", "Stats", "Stats.json"),
        )
        shutil.copy(
            "data/Stats.json",
            os.path.join(complex_run_dir, "Demultiplexing_1", "Stats", "Stats.json"),
        )
        shutil.copy(
            "data/lane.html",
            os.path.join(
                complex_run_dir,
                "Demultiplexing_0",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            ),
        )
        shutil.copy(
            "data/lane.html",
            os.path.join(
                complex_run_dir,
                "Demultiplexing_1",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            ),
        )
        shutil.copy(
            "data/laneBarcode.html",
            os.path.join(
                complex_run_dir,
                "Demultiplexing_0",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            ),
        )
        shutil.copy(
            "data/laneBarcode.html",
            os.path.join(
                complex_run_dir,
                "Demultiplexing_1",
                "Reports",
                "html",
                "FCIDXX",
                "all",
                "all",
                "all",
            ),
        )

        # Create archive dir
        self.archive_dir = os.path.join(self.tmp_dir, "archive")
        os.makedirs(self.archive_dir)

        # Create run objects
        self.running = Standard_Run(
            os.path.join(self.tmp_dir, "141124_ST-RUNNING1_03_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )
        self.to_start = Run(
            os.path.join(self.tmp_dir, "141124_ST-TOSTART1_04_FCIDXXX"),
            CONFIG["analysis"]["NovaSeq"],
        )
        self.in_progress = Standard_Run(
            os.path.join(self.tmp_dir, "141124_ST-INPROGRESS1_02_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )
        self.in_progress_done = Standard_Run(
            os.path.join(self.tmp_dir, "141124_ST-INPROGRESSDONE1_02_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )
        self.completed = Run(
            os.path.join(self.tmp_dir, "141124_ST-COMPLETED1_01_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )
        self.dummy_run = Run(
            os.path.join(self.tmp_dir, "141124_ST-DUMMY1_01_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )
        self.finished_runs = [self.to_start, self.in_progress, self.completed]
        self.complex_run = Run(
            os.path.join(self.tmp_dir, "141124_ST-COMPLEX1_01_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_run_setup(self):
        """Raise RuntimeError if files are missing."""
        # if rundir missing
        with self.assertRaises(RuntimeError):
            Run("missing_dir", CONFIG["analysis"]["NovaSeq"])
        # if config incomplete
        with self.assertRaises(RuntimeError):
            Run(self.tmp_dir, CONFIG["analysis"]["DummySeq"])
        # if runParameters.xml missing
        with self.assertRaises(RuntimeError):
            Run(self.tmp_dir, CONFIG["analysis"]["NovaSeq"])

    def test_is_sequencing_done(self):
        """Is finished should be True only if "RTAComplete.txt" file is present."""
        self.assertFalse(self.running._is_sequencing_done())
        self.assertTrue(all([run._is_sequencing_done for run in self.finished_runs]))

    def test_get_run_status(self):
        """Get the run status based on present files."""
        self.assertEqual("SEQUENCING", self.running.get_run_status())
        self.assertEqual("TO_START", self.to_start.get_run_status())
        self.assertEqual("IN_PROGRESS", self.in_progress.get_run_status())
        self.assertEqual("COMPLETED", self.completed.get_run_status())

    def test_is_transferred(self):
        """is_transferred should rely on the info in transfer.tsv."""
        os.makedirs(
            os.path.join(self.tmp_dir, "141124_ST-DUMMY1_01_AFCIDXX", "transferring")
        )
        self.assertTrue(self.dummy_run.is_transferred(self.transfer_file))
        self.assertTrue(self.completed.is_transferred(self.transfer_file))
        self.assertFalse(self.running.is_transferred(self.transfer_file))
        self.assertFalse(self.to_start.is_transferred(self.transfer_file))
        self.assertFalse(self.in_progress.is_transferred(self.transfer_file))
        self.assertFalse(self.completed.is_transferred("missing_file"))

    @mock.patch("taca.illumina.Standard_Runs.Standard_Run._aggregate_demux_results")
    def test_check_run_status_done(self, mock_aggregate_demux_results):
        """Recognize if a demultiplexing run is finished or not."""
        self.in_progress.check_run_status()
        mock_aggregate_demux_results.assert_not_called()
        self.in_progress_done.check_run_status()
        mock_aggregate_demux_results.assert_called_once()

    @mock.patch("taca.illumina.Runs.Run.get_run_status")
    def test_check_run_status_completed(self, mock_status):
        """Return None if run is finished."""
        mock_status.return_value = "COMPLETED"
        self.assertEqual(self.in_progress.check_run_status(), None)

    def test_get_run_type(self):
        """Return runtype if set."""
        self.assertEqual("NGI-RUN", self.running.get_run_type())
        self.to_start.run_type = False
        with self.assertRaises(RuntimeError):
            self.to_start.get_run_type()

    def test_get_demux_folder(self):
        """Return name of demux folder if set."""
        self.assertEqual("Demultiplexing", self.running._get_demux_folder())

    def test_get_samplesheet(self):
        """Return location of sample sheet."""
        self.assertEqual("data/2014/FCIDXX.csv", self.running._get_samplesheet())

    def test_is_demultiplexing_done(self):
        """Return true if Stats.json exists, else false."""
        self.assertFalse(self.in_progress._is_demultiplexing_done())
        self.assertTrue(self.completed._is_demultiplexing_done())

    def test_is_demultiplexing_started(self):
        """Return true if demux folder exists, else false."""
        self.assertTrue(self.in_progress._is_demultiplexing_started())
        self.assertFalse(self.to_start._is_demultiplexing_started())

    def test_generate_per_lane_base_mask(self):
        """Generate base mask."""
        with self.assertRaises(RuntimeError):
            self.dummy_run._generate_per_lane_base_mask()

        shutil.copy(
            "data/samplesheet_dummy_run.csv",
            os.path.join(
                self.tmp_dir, "141124_ST-DUMMY1_01_AFCIDXX", "SampleSheet.csv"
            ),
        )
        self.dummy_run._set_run_parser_obj(CONFIG["analysis"]["NovaSeq"])
        expected_mask = {
            "1": {
                "Y151I7N3I7N3": {
                    "base_mask": ["Y151", "I7N3", "I7N3"],
                    "data": [
                        {
                            "index": "CGCGCAG",
                            "Lane": "1",
                            "Sample_ID": "Sample_P10000_1001",
                            "Sample_Project": "A_Test_18_01",
                            "Sample_Name": "Sample_P10000_1001",
                            "index2": "CTGCGCG",
                        }
                    ],
                },
                "Y151I7N3N10": {
                    "base_mask": ["Y151", "I7N3", "N10"],
                    "data": [
                        {
                            "index": "AGGTACC",
                            "Lane": "1",
                            "Sample_ID": "Sample_P10000_1005",
                            "Sample_Project": "A_Test_18_01",
                            "Sample_Name": "Sample_P10000_1005",
                            "index2": "",
                        }
                    ],
                },
            }
        }
        got_mask = self.dummy_run._generate_per_lane_base_mask()
        self.assertEqual(expected_mask, got_mask)

    def test_compute_base_mask(self):
        """Compute Run base mask."""
        runSetup = [
            {"IsIndexedRead": "N", "NumCycles": "151", "Number": "1"},
            {"IsIndexedRead": "Y", "NumCycles": "8", "Number": "2"},
            {"IsIndexedRead": "Y", "NumCycles": "8", "Number": "3"},
            {"IsIndexedRead": "N", "NumCycles": "151", "Number": "4"},
        ]
        index_size = 7
        dual_index_sample = True
        index2_size = 7
        got_mask = self.dummy_run._compute_base_mask(
            runSetup, index_size, dual_index_sample, index2_size
        )
        expected_mask = ["Y151", "I7N1", "I7N1", "Y151"]
        self.assertEqual(got_mask, expected_mask)

    @mock.patch("taca.illumina.Runs.misc.call_external_command")
    def test_transfer_run(self, mock_call_external_command):
        """Call external rsync."""
        self.completed.transfer_run(self.transfer_file)
        command_line = [
            "rsync",
            "-LtDrv",
            "--chmod=g+rw",
            "--exclude=Demultiplexing_*/*_*",
            "--include=*/",
            "--include=*.file",
            "--exclude=*",
            "--prune-empty-dirs",
            os.path.join(self.tmp_dir, "141124_ST-COMPLETED1_01_AFCIDXX"),
            "None@None:None",
        ]
        mock_call_external_command.assert_called_once_with(
            command_line,
            log_dir=os.path.join(self.tmp_dir, "141124_ST-COMPLETED1_01_AFCIDXX"),
            prefix="",
            with_log_files=True,
        )

    @mock.patch("taca.illumina.Runs.misc.call_external_command")
    def test_transfer_run_error(self, mock_call_external_command):
        """Handle external rsync error."""
        mock_call_external_command.side_effect = subprocess.CalledProcessError(
            1, "some error"
        )
        with self.assertRaises(subprocess.CalledProcessError):
            self.completed.transfer_run(self.transfer_file)

    @mock.patch("taca.illumina.Runs.shutil.move")
    def test_archive_run(self, mock_move):
        """Move file to archive."""
        self.completed.archive_run(self.archive_dir)
        mock_move.assert_called_once_with(
            os.path.join(self.tmp_dir, "141124_ST-COMPLETED1_01_AFCIDXX"),
            os.path.join(self.archive_dir, "141124_ST-COMPLETED1_01_AFCIDXX"),
        )

    @mock.patch("taca.illumina.Runs.misc.send_mail")
    def test_send_mail(self, mock_send_mail):
        """Send mail to user."""
        self.completed.send_mail("Hello", "user@email.com")
        mock_send_mail.assert_called_once_with(
            "141124_ST-COMPLETED1_01_AFCIDXX", "Hello", "user@email.com"
        )

    def test_is_unpooled_lane(self):
        """Check if lane is unpooled."""
        self.assertTrue(self.in_progress.is_unpooled_lane("2"))

    def test_get_samples_per_lane(self):
        """Return samples from samplesheet."""
        expected_samples = {
            "1": "P10000_1001",
            "2": "P10000_1005",
            "3": "P10000_1006",
            "4": "P10000_1007",
        }
        got_samples = self.in_progress.get_samples_per_lane()
        self.assertEqual(expected_samples, got_samples)

    @mock.patch("taca.illumina.Runs.os.rename")
    def test_rename_undet(self, mock_rename):
        """Prepend sample name to file name."""
        samples_per_lane = {"1": "P10000_1001", "2": "P10000_1005"}
        lane = "1"
        self.completed._rename_undet(lane, samples_per_lane)
        old_name = os.path.join(
            self.tmp_dir,
            "141124_ST-COMPLETED1_01_AFCIDXX",
            "Demultiplexing",
            "Undetermined_S0_L001_R1_001.fastq.gz",
        )
        new_name = os.path.join(
            self.tmp_dir,
            "141124_ST-COMPLETED1_01_AFCIDXX",
            "Demultiplexing",
            "P10000_1001_Undetermined_L011_R1_001.fastq.gz",
        )
        mock_rename.assert_called_once_with(old_name, new_name)

    @mock.patch("taca.illumina.Runs.os.symlink")
    def test_aggregate_demux_results_simple_complex(self, mock_symlink):
        """Aggregare demux results simple case."""
        self.assertTrue(self.in_progress_done._aggregate_demux_results_simple_complex())
        calls = [
            mock.call(
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing_0/Stats/DemultiplexingStats.xml",
                ),
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing/Stats/DemultiplexingStats.xml",
                ),
            ),
            mock.call(
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing_0/Stats/AdapterTrimming.txt",
                ),
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing/Stats/AdapterTrimming.txt",
                ),
            ),
            mock.call(
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing_0/Stats/ConversionStats.xml",
                ),
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing/Stats/ConversionStats.xml",
                ),
            ),
            mock.call(
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing_0/Stats/Stats.json",
                ),
                os.path.join(
                    self.tmp_dir,
                    "141124_ST-INPROGRESSDONE1_02_AFCIDXX/Demultiplexing/Stats/Stats.json",
                ),
            ),
        ]
        mock_symlink.assert_has_calls(calls)

    @mock.patch("taca.illumina.Runs.json.dump")
    def test_aggregate_demux_results_simple_complex_complex(self, mock_json_dump):
        """Aggregare demux results complex case."""
        self.assertTrue(self.complex_run._aggregate_demux_results_simple_complex())
        mock_json_dump.assert_called_once()

    def test_aggregate_demux_results_simple_complex_fail(self):
        """Aggregate_demux_results_simple_complex should raise error if files are missing."""
        with self.assertRaises(RuntimeError):
            self.in_progress_done._aggregate_demux_results_simple_complex()

    def test_create_folder_structure(self):
        """Make directory structure."""
        root = self.tmp_dir
        dirs = ["dir1", "dir2"]
        path = _create_folder_structure(root, dirs)
        self.assertEqual(path, os.path.join(self.tmp_dir, "dir1/dir2"))

    def test_generate_lane_html(self):
        """Generate lane HTML."""
        html_report = "data/lane.html"
        html_report_lane_parser = LaneBarcodeParser(html_report)
        html_file = os.path.join(self.tmp_dir, "generated_lane.html")
        expected_file = "data/lane_result.html"
        _generate_lane_html(html_file, html_report_lane_parser)
        self.assertTrue(filecmp.cmp(html_file, expected_file))


class TestNovaSeqRuns(unittest.TestCase):
    """Tests for the NovaSeq_Run run class."""

    @classmethod
    def setUpClass(self):
        """Creates the following directory tree for testing purposes:

        tmp/
        |__ 141124_ST-RUNNING1_03_AFCIDXX
            |__ RunInfo.xml
        """
        self.tmp_dir = os.path.join(tempfile.mkdtemp(), "tmp")

        running = os.path.join(self.tmp_dir, "141124_ST-RUNNING1_03_AFCIDXX")
        os.makedirs(self.tmp_dir)
        os.makedirs(running)

        # Create files indicating that the run is finished
        open(os.path.join(running, "RTAComplete.txt"), "w").close()

        # Move sample RunInfo.xml file to run directory
        shutil.copy("data/RunInfo.xml", running)
        shutil.copy("data/runParameters.xml", running)

        # Create run objects
        self.running = NovaSeq_Run(
            os.path.join(self.tmp_dir, "141124_ST-RUNNING1_03_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_novaseq(self):
        """Set sequencer and run type NovaSeq."""
        self.assertEqual(self.running.sequencer_type, "NovaSeq")
        self.assertEqual(self.running.run_type, "NGI-RUN")


class TestNextSeqRuns(unittest.TestCase):
    """Tests for the NextSeq_Run run class."""

    @classmethod
    def setUpClass(self):
        """Creates the following directory tree for testing purposes:

        tmp/
        |__ 141124_ST-RUNNING1_03_AFCIDXX
            |__ RunInfo.xml
        """
        self.tmp_dir = os.path.join(tempfile.mkdtemp(), "tmp")

        running = os.path.join(self.tmp_dir, "141124_ST-RUNNING1_03_AFCIDXX")
        os.makedirs(self.tmp_dir)
        os.makedirs(running)

        # Create files indicating that the run is finished
        open(os.path.join(running, "RTAComplete.txt"), "w").close()

        # Move sample RunInfo.xml file to run directory
        shutil.copy("data/RunInfo.xml", running)
        shutil.copy("data/runParameters.xml", running)

        # Create run objects
        self.running = NextSeq_Run(
            os.path.join(self.tmp_dir, "141124_ST-RUNNING1_03_AFCIDXX"),
            CONFIG["analysis"]["NovaSeq"],
        )

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_nextseq(self):
        """Set sequencer and run type NextSeq."""
        self.assertEqual(self.running.sequencer_type, "NextSeq")
        self.assertEqual(self.running.run_type, "NGI-RUN")
