# Allows: python -m history_quiz [subcommand]
from .main import cli

if __name__ == "__main__":
    raise SystemExit(cli())