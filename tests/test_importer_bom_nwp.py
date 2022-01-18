# -*- coding: utf-8 -*-

import os

import pytest

import pysteps
from pysteps.io import interface
from pysteps.tests.helpers import smart_assert

pytest.importorskip("netCDF4")


def test_importers_discovery():
    """Check if the importer plugin is correctly detected by pysteps. For this,
    the tests should be ran on the installed version of the plugin (and not
    against the plugin sources).
    """
    new_importers = ["import_bom_nwp"]
    for importer in new_importers:
        assert importer.replace("import_", "") in interface._importer_methods 

root_path = pysteps.rcparams.data_sources["bom_nwp"]["root_path"]
rel_path = os.path.join("2020", "10", "31")
filename = os.path.join(root_path, rel_path, "20201031_0000_regrid_short.nc")
importer = pysteps.io.get_method("bom_nwp", "importer")
precip_nwp, _, metadata_nwp = importer(filename)

expected_proj = "+proj=aea  +lon_0=153.240 +lat_0=-27.718 +lat_1=-26.200 +lat_2=-29.300"

def test_io_import_bom_nwp_shape():
    """Test the BoM NWP importer shape."""
    assert precip_nwp.shape == (144, 512, 512)

test_attrs_bom = [
    ("projection", expected_proj, None),
    ("institution", "Commonwealth of Australia, Bureau of Meteorology", None),
    ("transform", None, None),
    ("zerovalue", 0.0, 0.1),
    ("unit", "mm", None),
    ("accutime", 10, None),
    ("xpixelsize", 500.0, 0.1),
    ("ypixelsize", 500.0, 0.1),
    ("yorigin", "upper", None),
    ("cartesian_unit", "m", None),
    ("x1", -127750.0, 0.1),
    ("x2", 127750.0, 0.1),
    ("y1", -127750.0, 0.1),
    ("y2", 127750.0, 0.1),
]

@pytest.mark.parametrize("variable, expected, tolerance", test_attrs_bom)
def test_io_import_bom_nwp(variable, expected, tolerance):
    """Test the BoM NWP importer."""
    smart_assert(metadata_nwp[variable], expected, tolerance)