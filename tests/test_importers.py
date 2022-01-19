from collections import namedtuple, defaultdict

import pytest

from pysteps_nwp_importers.importer_bom_nwp import import_bom_nwp
from pysteps_nwp_importers.importer_knmi_nwp import import_knmi_nwp
from pysteps_nwp_importers.importer_rmi_nwp import import_rmi_nwp

pytest.importorskip("netCDF4")

ImportedData = namedtuple(
    "ImportedData", ["data", "expected_shape", "metadata", "expected_metadata"]
)

TOLERANCE = defaultdict(lambda: 0.0001)
TOLERANCE["threshold"] = 0.01


def rmi_imported_data():
    rmi_precip_data, _, metadata_nwp = import_rmi_nwp(
        "data/rmi/ao13_2021070412_native_5min.nc"
    )
    expected_proj = (
        "+proj=lcc +lon_0=4.55 +lat_1=50.8 +lat_2=50.8 "
        "+a=6371229 +es=0 +lat_0=50.8 +x_0=365950 +y_0=-365950.000000001"
    )
    expected_shape = (24, 564, 564)
    expected_metadata = dict(
        projection=expected_proj,
        institution="Royal Meteorological Institute of Belgium",
        transform=None,
        zerovalue=0.0,
        threshold=0,
        unit="mm",
        accutime=5,
        xpixelsize=1300.0,
        ypixelsize=1300.0,
        yorigin="upper",
        cartesian_unit="m",
        x1=0.0,
        x2=731900.0,
        y1=-731900.0,
        y2=0.0,
    )
    return ImportedData(
        data=rmi_precip_data,
        metadata=metadata_nwp,
        expected_shape=expected_shape,
        expected_metadata=expected_metadata,
    )


def bom_imported_data():
    precip_data, _, metadata_nwp = import_bom_nwp(
        "data/bom/20201031_0000_regrid_short.nc"
    )
    expected_proj = (
        "+proj=aea  +lon_0=153.240 +lat_0=-27.718 +lat_1=-26.200 +lat_2=-29.300"
    )
    expected_shape = (144, 512, 512)
    expected_metadata = dict(
        projection=expected_proj,
        institution="Commonwealth of Australia, Bureau of Meteorology",
        transform=None,
        zerovalue=0.0,
        threshold=0,
        unit="mm",
        accutime=10,
        xpixelsize=500.0,
        ypixelsize=500.0,
        yorigin="upper",
        cartesian_unit="m",
        x1=-127750.0,
        x2=127750.0,
        y1=-127750.0,
        y2=127750.0,
    )

    return ImportedData(
        data=precip_data,
        expected_shape=expected_shape,
        metadata=metadata_nwp,
        expected_metadata=expected_metadata,
    )


def kmni_imported_data():
    precip_data, _, metadata_nwp = import_knmi_nwp(
        "data/knmi/20180905_0600_Pforecast_Harmonie.nc"
    )
    expected_proj = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
    expected_shape = (49, 300, 300)
    expected_metadata = dict(
        projection=expected_proj,
        institution="  Royal Netherlands Meteorological Institute (KNMI)  ",
        transform=None,
        zerovalue=0.0,
        threshold=0,
        unit="mm",
        accutime=60,
        xpixelsize=0.037,
        ypixelsize=0.023,
        yorigin="lower",
        cartesian_unit="degrees_east",
        x1=0,
        x2=11.063,
        y1=49.0,
        y2=55.877,
    )

    return ImportedData(
        data=precip_data,
        expected_shape=expected_shape,
        metadata=metadata_nwp,
        expected_metadata=expected_metadata,
    )


@pytest.fixture(
    scope="class", params=(rmi_imported_data, bom_imported_data, kmni_imported_data)
)
def imported_data(request):
    return request.param()


class Test_Importer:
    def test_data_shape_is_correct(self, imported_data):
        assert imported_data.data.shape == imported_data.expected_shape

    def test_attributes_are_loaded_correctly(self, imported_data):
        expected_metadata = imported_data.expected_metadata
        obtained_metadata = imported_data.metadata

        assert set(expected_metadata.keys()) == set(obtained_metadata.keys())

        for attr_name, expected_value in expected_metadata.items():
            obtained_value = obtained_metadata[attr_name]
            if isinstance(expected_value, str):
                assert obtained_value == expected_value
            else:
                assert obtained_value == pytest.approx(
                    expected_value, rel=TOLERANCE[attr_name], abs=TOLERANCE[attr_name]
                )
