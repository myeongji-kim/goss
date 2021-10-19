import pytest


def pytest_addoption(parser):
    parser.addoption("--region", action="store", default="kr", help="kr, us, jp, eu")


@pytest.fixture
def region(request):
    return request.config.getoption("--region")
