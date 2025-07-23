def load_dotenv(path=None, override=False):
    """Minimal stub for tests. Does nothing except optionally read .env file."""
    if path:
        try:
            with open(path) as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, val = line.strip().split('=', 1)
                        import os
                        if override or key not in os.environ:
                            os.environ[key] = val
        except FileNotFoundError:
            pass
    return True
