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
    new_importers = ["import_knmi_nwp"]
    for importer in new_importers:
        assert importer.replace("import_", "") in interface._importer_methods


root_path = "./nwp/knmi"
rel_path = os.path.join("2018", "09", "05")
filename = os.path.join(root_path, rel_path, "20180905_0600_Pforecast_Harmonie.nc")
importer = pysteps.io.get_method("knmi_nwp", "importer")
precip_nwp, _, metadata_nwp = importer(filename)

expected_proj = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"


def test_io_import_knmi_nwp_shape():
    """Test the KNMI NWP importer shape."""
    assert precip_nwp.shape == (49, 300, 300)


test_attrs_knmi = [
    ("projection", expected_proj, None),
    ("institution", "  Royal Netherlands Meteorological Institute (KNMI)  ", None),
    ("transform", None, None),
    ("zerovalue", 0.0, 0.1),
    ("unit", "mm", None),
    ("accutime", 60, None),
    ("xpixelsize", 0.037, 0.0001),
    ("ypixelsize", 0.023, 0.0001),
    ("yorigin", "lower", None),
    ("cartesian_unit", "degrees_east", None),
    ("x1", 0.0, 0.0001),
    ("x2", 11.063, 0.0001),
    ("y1", 49.0, 0.0001),
    ("y2", 55.877, 0.0001),
]


@pytest.mark.parametrize("variable, expected, tolerance", test_attrs_knmi)
def test_io_import_knmi_nwp(variable, expected, tolerance):
    """Test the KNMI Harmonie NWP importer."""
    smart_assert(metadata_nwp[variable], expected, tolerance)
