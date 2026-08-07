"""Application entry point."""

from app.app import DiskBenchApp


def main() -> None:
    """Start the terminal application."""
    DiskBenchApp().run()
