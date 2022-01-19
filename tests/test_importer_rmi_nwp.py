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
    new_importers = ["import_rmi_nwp"]
    for importer in new_importers:
        assert importer.replace("import_", "") in interface._importer_methods


# Finally, test the RMI NWP importer
root_path = "./nwp/rmi"
rel_path = os.path.join("2021", "07", "04")
filename = os.path.join(root_path, rel_path, "ao13_2021070412_native_5min.nc")
importer = pysteps.io.get_method("rmi_nwp", "importer")
precip_nwp, _, metadata_nwp = importer(filename)

expected_proj = "+proj=lcc +lon_0=4.55 +lat_1=50.8 +lat_2=50.8 +a=6371229 +es=0 +lat_0=50.8 +x_0=365950 +y_0=-365950.000000001"


def test_io_import_rmi_nwp_shape():
    """Test the RMI NWP importer shape."""
    assert precip_nwp.shape == (24, 564, 564)


test_attrs_rmi = [
    ("projection", expected_proj, None),
    ("institution", "Royal Meteorological Institute of Belgium", None),
    ("transform", None, None),
    ("zerovalue", 0.0, 0.1),
    ("unit", "mm", None),
    ("accutime", 5, None),
    ("xpixelsize", 1300.0, 0.1),
    ("ypixelsize", 1300.0, 0.1),
    ("yorigin", "upper", None),
    ("cartesian_unit", "m", None),
    ("x1", 0, 0.1),
    ("x2", 731900.0, 0.1),
    ("y1", -731900.0, 0.1),
    ("y2", 0.0, 0.1),
]


@pytest.mark.parametrize("variable, expected, tolerance", test_attrs_rmi)
def test_io_import_rmi_nwp(variable, expected, tolerance):
    """Test the RMI NWP importer."""
    smart_assert(metadata_nwp[variable], expected, tolerance)
