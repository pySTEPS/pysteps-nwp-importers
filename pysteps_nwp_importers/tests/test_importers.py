from collections import namedtuple, defaultdict
from pathlib import Path

import numpy as np
import pytest

from pysteps_nwp_importers.importer_bom_nwp import import_bom_nwp
from pysteps_nwp_importers.importer_knmi_nwp import import_knmi_nwp
from pysteps_nwp_importers.importer_rmi_nwp import import_rmi_nwp
from pysteps_nwp_importers.tests.download_test_data import download_test_data

pytest.importorskip("netCDF4")

ImportedData = namedtuple(
    "ImportedData", ["data", "expected_shape", "metadata", "expected_metadata"]
)

TOLERANCE = defaultdict(lambda: 0.0001)
TOLERANCE["threshold"] = 0.01

download_test_data()
DATA_DIR = Path(__file__).parent / "data"


def rmi_imported_data():
    rmi_precip_data, _, metadata_nwp = import_rmi_nwp(
        str(DATA_DIR / "rmi/ao13_2021070412_native_5min.nc")
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
        time_stamps=np.array(
            [
                "2021-07-04T16:05:00.000000000",
                "2021-07-04T16:10:00.000000000",
                "2021-07-04T16:15:00.000000000",
                "2021-07-04T16:20:00.000000000",
                "2021-07-04T16:25:00.000000000",
                "2021-07-04T16:30:00.000000000",
                "2021-07-04T16:35:00.000000000",
                "2021-07-04T16:40:00.000000000",
                "2021-07-04T16:45:00.000000000",
                "2021-07-04T16:50:00.000000000",
                "2021-07-04T16:55:00.000000000",
                "2021-07-04T17:00:00.000000000",
                "2021-07-04T17:05:00.000000000",
                "2021-07-04T17:10:00.000000000",
                "2021-07-04T17:15:00.000000000",
                "2021-07-04T17:20:00.000000000",
                "2021-07-04T17:25:00.000000000",
                "2021-07-04T17:30:00.000000000",
                "2021-07-04T17:35:00.000000000",
                "2021-07-04T17:40:00.000000000",
                "2021-07-04T17:45:00.000000000",
                "2021-07-04T17:50:00.000000000",
                "2021-07-04T17:55:00.000000000",
                "2021-07-04T18:00:00.000000000",
            ],
            dtype="datetime64[ns]",
        ),
    )
    return ImportedData(
        data=rmi_precip_data,
        metadata=metadata_nwp,
        expected_shape=expected_shape,
        expected_metadata=expected_metadata,
    )


def bom_imported_data():
    precip_data, _, metadata_nwp = import_bom_nwp(
        str(DATA_DIR / "bom/20201031_0000_regrid_short.nc")
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
        time_stamps=np.array(
            [
                "2020-10-31T00:00:00.000000000",
                "2020-10-31T00:10:00.000000000",
                "2020-10-31T00:20:00.000000000",
                "2020-10-31T00:30:00.000000000",
                "2020-10-31T00:40:00.000000000",
                "2020-10-31T00:50:00.000000000",
                "2020-10-31T01:00:00.000000000",
                "2020-10-31T01:10:00.000000000",
                "2020-10-31T01:20:00.000000000",
                "2020-10-31T01:30:00.000000000",
                "2020-10-31T01:40:00.000000000",
                "2020-10-31T01:50:00.000000000",
                "2020-10-31T02:00:00.000000000",
                "2020-10-31T02:10:00.000000000",
                "2020-10-31T02:20:00.000000000",
                "2020-10-31T02:30:00.000000000",
                "2020-10-31T02:40:00.000000000",
                "2020-10-31T02:50:00.000000000",
                "2020-10-31T03:00:00.000000000",
                "2020-10-31T03:10:00.000000000",
                "2020-10-31T03:20:00.000000000",
                "2020-10-31T03:30:00.000000000",
                "2020-10-31T03:40:00.000000000",
                "2020-10-31T03:50:00.000000000",
                "2020-10-31T04:00:00.000000000",
                "2020-10-31T04:10:00.000000000",
                "2020-10-31T04:20:00.000000000",
                "2020-10-31T04:30:00.000000000",
                "2020-10-31T04:40:00.000000000",
                "2020-10-31T04:50:00.000000000",
                "2020-10-31T05:00:00.000000000",
                "2020-10-31T05:10:00.000000000",
                "2020-10-31T05:20:00.000000000",
                "2020-10-31T05:30:00.000000000",
                "2020-10-31T05:40:00.000000000",
                "2020-10-31T05:50:00.000000000",
                "2020-10-31T06:00:00.000000000",
                "2020-10-31T06:10:00.000000000",
                "2020-10-31T06:20:00.000000000",
                "2020-10-31T06:30:00.000000000",
                "2020-10-31T06:40:00.000000000",
                "2020-10-31T06:50:00.000000000",
                "2020-10-31T07:00:00.000000000",
                "2020-10-31T07:10:00.000000000",
                "2020-10-31T07:20:00.000000000",
                "2020-10-31T07:30:00.000000000",
                "2020-10-31T07:40:00.000000000",
                "2020-10-31T07:50:00.000000000",
                "2020-10-31T08:00:00.000000000",
                "2020-10-31T08:10:00.000000000",
                "2020-10-31T08:20:00.000000000",
                "2020-10-31T08:30:00.000000000",
                "2020-10-31T08:40:00.000000000",
                "2020-10-31T08:50:00.000000000",
                "2020-10-31T09:00:00.000000000",
                "2020-10-31T09:10:00.000000000",
                "2020-10-31T09:20:00.000000000",
                "2020-10-31T09:30:00.000000000",
                "2020-10-31T09:40:00.000000000",
                "2020-10-31T09:50:00.000000000",
                "2020-10-31T10:00:00.000000000",
                "2020-10-31T10:10:00.000000000",
                "2020-10-31T10:20:00.000000000",
                "2020-10-31T10:30:00.000000000",
                "2020-10-31T10:40:00.000000000",
                "2020-10-31T10:50:00.000000000",
                "2020-10-31T11:00:00.000000000",
                "2020-10-31T11:10:00.000000000",
                "2020-10-31T11:20:00.000000000",
                "2020-10-31T11:30:00.000000000",
                "2020-10-31T11:40:00.000000000",
                "2020-10-31T11:50:00.000000000",
                "2020-10-31T12:00:00.000000000",
                "2020-10-31T12:10:00.000000000",
                "2020-10-31T12:20:00.000000000",
                "2020-10-31T12:30:00.000000000",
                "2020-10-31T12:40:00.000000000",
                "2020-10-31T12:50:00.000000000",
                "2020-10-31T13:00:00.000000000",
                "2020-10-31T13:10:00.000000000",
                "2020-10-31T13:20:00.000000000",
                "2020-10-31T13:30:00.000000000",
                "2020-10-31T13:40:00.000000000",
                "2020-10-31T13:50:00.000000000",
                "2020-10-31T14:00:00.000000000",
                "2020-10-31T14:10:00.000000000",
                "2020-10-31T14:20:00.000000000",
                "2020-10-31T14:30:00.000000000",
                "2020-10-31T14:40:00.000000000",
                "2020-10-31T14:50:00.000000000",
                "2020-10-31T15:00:00.000000000",
                "2020-10-31T15:10:00.000000000",
                "2020-10-31T15:20:00.000000000",
                "2020-10-31T15:30:00.000000000",
                "2020-10-31T15:40:00.000000000",
                "2020-10-31T15:50:00.000000000",
                "2020-10-31T16:00:00.000000000",
                "2020-10-31T16:10:00.000000000",
                "2020-10-31T16:20:00.000000000",
                "2020-10-31T16:30:00.000000000",
                "2020-10-31T16:40:00.000000000",
                "2020-10-31T16:50:00.000000000",
                "2020-10-31T17:00:00.000000000",
                "2020-10-31T17:10:00.000000000",
                "2020-10-31T17:20:00.000000000",
                "2020-10-31T17:30:00.000000000",
                "2020-10-31T17:40:00.000000000",
                "2020-10-31T17:50:00.000000000",
                "2020-10-31T18:00:00.000000000",
                "2020-10-31T18:10:00.000000000",
                "2020-10-31T18:20:00.000000000",
                "2020-10-31T18:30:00.000000000",
                "2020-10-31T18:40:00.000000000",
                "2020-10-31T18:50:00.000000000",
                "2020-10-31T19:00:00.000000000",
                "2020-10-31T19:10:00.000000000",
                "2020-10-31T19:20:00.000000000",
                "2020-10-31T19:30:00.000000000",
                "2020-10-31T19:40:00.000000000",
                "2020-10-31T19:50:00.000000000",
                "2020-10-31T20:00:00.000000000",
                "2020-10-31T20:10:00.000000000",
                "2020-10-31T20:20:00.000000000",
                "2020-10-31T20:30:00.000000000",
                "2020-10-31T20:40:00.000000000",
                "2020-10-31T20:50:00.000000000",
                "2020-10-31T21:00:00.000000000",
                "2020-10-31T21:10:00.000000000",
                "2020-10-31T21:20:00.000000000",
                "2020-10-31T21:30:00.000000000",
                "2020-10-31T21:40:00.000000000",
                "2020-10-31T21:50:00.000000000",
                "2020-10-31T22:00:00.000000000",
                "2020-10-31T22:10:00.000000000",
                "2020-10-31T22:20:00.000000000",
                "2020-10-31T22:30:00.000000000",
                "2020-10-31T22:40:00.000000000",
                "2020-10-31T22:50:00.000000000",
                "2020-10-31T23:00:00.000000000",
                "2020-10-31T23:10:00.000000000",
                "2020-10-31T23:20:00.000000000",
                "2020-10-31T23:30:00.000000000",
                "2020-10-31T23:40:00.000000000",
                "2020-10-31T23:50:00.000000000",
                "2020-11-01T00:00:00.000000000",
            ],
            dtype="datetime64[ns]",
        ),
    )

    return ImportedData(
        data=precip_data,
        expected_shape=expected_shape,
        metadata=metadata_nwp,
        expected_metadata=expected_metadata,
    )


def kmni_imported_data():
    precip_data, _, metadata_nwp = import_knmi_nwp(
        str(DATA_DIR / "knmi/20180905_0600_Pforecast_Harmonie.nc")
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
        time_stamps=np.array(
            [
                "2018-09-05T06:00:00.000000000",
                "2018-09-05T07:00:00.000000000",
                "2018-09-05T08:00:00.000000000",
                "2018-09-05T09:00:00.000000000",
                "2018-09-05T10:00:00.000000000",
                "2018-09-05T11:00:00.000000000",
                "2018-09-05T12:00:00.000000000",
                "2018-09-05T13:00:00.000000000",
                "2018-09-05T14:00:00.000000000",
                "2018-09-05T15:00:00.000000000",
                "2018-09-05T16:00:00.000000000",
                "2018-09-05T17:00:00.000000000",
                "2018-09-05T18:00:00.000000000",
                "2018-09-05T19:00:00.000000000",
                "2018-09-05T20:00:00.000000000",
                "2018-09-05T21:00:00.000000000",
                "2018-09-05T22:00:00.000000000",
                "2018-09-05T23:00:00.000000000",
                "2018-09-06T00:00:00.000000000",
                "2018-09-06T01:00:00.000000000",
                "2018-09-06T02:00:00.000000000",
                "2018-09-06T03:00:00.000000000",
                "2018-09-06T04:00:00.000000000",
                "2018-09-06T05:00:00.000000000",
                "2018-09-06T06:00:00.000000000",
                "2018-09-06T07:00:00.000000000",
                "2018-09-06T08:00:00.000000000",
                "2018-09-06T09:00:00.000000000",
                "2018-09-06T10:00:00.000000000",
                "2018-09-06T11:00:00.000000000",
                "2018-09-06T12:00:00.000000000",
                "2018-09-06T13:00:00.000000000",
                "2018-09-06T14:00:00.000000000",
                "2018-09-06T15:00:00.000000000",
                "2018-09-06T16:00:00.000000000",
                "2018-09-06T17:00:00.000000000",
                "2018-09-06T18:00:00.000000000",
                "2018-09-06T19:00:00.000000000",
                "2018-09-06T20:00:00.000000000",
                "2018-09-06T21:00:00.000000000",
                "2018-09-06T22:00:00.000000000",
                "2018-09-06T23:00:00.000000000",
                "2018-09-07T00:00:00.000000000",
                "2018-09-07T01:00:00.000000000",
                "2018-09-07T02:00:00.000000000",
                "2018-09-07T03:00:00.000000000",
                "2018-09-07T04:00:00.000000000",
                "2018-09-07T05:00:00.000000000",
                "2018-09-07T06:00:00.000000000",
            ],
            dtype="datetime64[ns]",
        ),
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
