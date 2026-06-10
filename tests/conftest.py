import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from image_plane import db as dbmod  # noqa: E402


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory):
    """Generate the synthetic image set once per test session."""
    import generate_test_images

    out = tmp_path_factory.mktemp("generated")
    generate_test_images.main(out)
    return out


@pytest.fixture()
def conn(tmp_path):
    c = dbmod.connect(tmp_path / "test.db")
    yield c
    c.close()
