import logging
import os
from importlib.metadata import entry_points

import click

import taca.log
from taca import __version__
from taca.utils import config as conf

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(__version__)
# Priority for the configuration file is: environment variable > -c option > default
@click.option(
    "-c",
    "--config-file",
    default=os.path.join(os.environ["HOME"], ".taca/taca.yaml"),
    envvar="TACA_CONFIG",
    type=click.File("r"),
    help="Path to TACA configuration file",
)
@click.pass_context
def cli(ctx, config_file):
    """Tool for the Automation of Storage and Analyses"""
    ctx.obj = {}
    config = conf.load_yaml_config(config_file.name)
    log_file = config.get("log", {}).get("file", None)
    if log_file:
        level = config.get("log").get("log_level", "INFO")
        taca.log.init_logger_file(log_file, level)
    logger.debug("starting up CLI")


# Add subcommands dynamically to the CLI
for entry_point in entry_points(group="taca.subcommands"):
    cli.add_command(entry_point.load())
