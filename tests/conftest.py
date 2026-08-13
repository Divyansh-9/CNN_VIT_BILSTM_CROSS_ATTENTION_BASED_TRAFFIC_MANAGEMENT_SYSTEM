"""Shared pytest configuration."""


def pytest_addoption(parser):
    parser.addoption(
        "--run-pretrained",
        action="store_true",
        default=False,
        help="run tests that download real backbone weights (~200 MB)",
    )
