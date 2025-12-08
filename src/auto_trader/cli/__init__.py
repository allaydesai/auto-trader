"""Command-line interface components."""

__all__ = ["cli", "validate_config", "setup", "help_system"]


def __getattr__(name):
    """Lazily import CLI entrypoints to avoid heavy startup dependencies."""
    if name in __all__:
        from .commands import cli, validate_config, setup, help_system

        exports = {
            "cli": cli,
            "validate_config": validate_config,
            "setup": setup,
            "help_system": help_system,
        }
        return exports[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")
