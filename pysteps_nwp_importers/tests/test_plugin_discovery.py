import subprocess
import sys

import pytest
from pysteps.io import interface

new_importers = [
    "import_bom_nwp",
    "import_knmi_nwp",
    "import_rmi_nwp",
    "import_dwd_nwp",
]


@pytest.mark.parametrize("importer_name", new_importers)
def test_importers_discovery(importer_name):
    """Check if the importer plugin is correctly detected by pysteps. For this,
    the tests should be ran on the installed version of the plugin (and not
    against the plugin sources).
    """
    assert importer_name.replace("import_", "") in interface._importer_methods


@pytest.mark.parametrize(
    "statement",
    [
        "import pysteps_nwp_importers; import pysteps",
        "import pysteps; import pysteps_nwp_importers",
    ],
)
def test_import_order(statement):
    """Importing pysteps loads the importer plugins. Check that this does not
    lead to a circular import when the plugin is imported before pysteps. This
    needs a fresh interpreter, since pysteps is already imported here.
    """
    check = (
        "from pysteps.io import interface; "
        "assert 'bom_nwp' in interface._importer_methods"
    )
    subprocess.run([sys.executable, "-c", f"{statement}; {check}"], check=True)
