import os


def stray() -> str:
    return os.environ["STRAY_UNDECLARED_KEY"]
