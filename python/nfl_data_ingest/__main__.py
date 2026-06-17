"""Allow ``python -m nfl_data_ingest`` to invoke the CLI."""
import sys

from nfl_data_ingest.cli import main

sys.exit(main())
