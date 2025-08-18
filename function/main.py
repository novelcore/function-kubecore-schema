"""The composition function's main CLI."""

import os
import click
from crossplane.function import logging, runtime

from function import fn


@click.command()
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    help="Emit debug logs.",
)
@click.option(
    "--address",
    default="0.0.0.0:9443",
    show_default=True,
    help="Address at which to listen for gRPC connections",
)
@click.option(
    "--tls-certs-dir",
    help="Serve using mTLS certificates.",
    envvar="TLS_SERVER_CERTS_DIR",
)
@click.option(
    "--insecure",
    is_flag=True,
    help="Run without mTLS credentials. "
    "If you supply this flag --tls-certs-dir will be ignored.",
)
def cli(debug: bool, address: str, tls_certs_dir: str, insecure: bool) -> None:  # noqa:FBT001  # We only expect callers via the CLI.
    """A Crossplane composition function."""
    try:
        # Check for LOG_LEVEL environment variable first
        log_level_env = os.getenv("LOG_LEVEL", "").upper()
        if log_level_env == "DEBUG":
            level = logging.Level.DEBUG
        elif log_level_env == "INFO":
            level = logging.Level.INFO
        elif log_level_env == "WARNING" or log_level_env == "WARN":
            level = logging.Level.WARNING
        elif log_level_env == "ERROR":
            level = logging.Level.ERROR
        elif debug:
            level = logging.Level.DEBUG
        else:
            level = logging.Level.INFO
        
        logging.configure(level=level)
        
        # Log startup information
        logger = logging.get_logger()
        logger.info(f"Starting KubeCore function with log level: {level}")
        if log_level_env:
            logger.debug(f"Log level set via environment variable: LOG_LEVEL={log_level_env}")
        elif debug:
            logger.debug("Debug mode enabled via CLI flag")
        logger.debug(f"Environment variables checked: LOG_LEVEL={os.getenv('LOG_LEVEL', 'not set')}")
        logger.debug(f"Server address: {address}")
        logger.debug(f"TLS certs dir: {tls_certs_dir}")
        logger.debug(f"Insecure mode: {insecure}")
        runtime.serve(
            fn.FunctionRunner(),
            address,
            creds=runtime.load_credentials(tls_certs_dir),
            insecure=insecure,
        )
    except Exception as e:
        logger = logging.get_logger()
        logger.error(f"Function startup failed: {e}")
        click.echo(f"Cannot run function: {e}")


if __name__ == "__main__":
    cli()
