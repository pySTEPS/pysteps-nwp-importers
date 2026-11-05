from datetime import datetime
from pathlib import Path

import numpy as np
import pyproj
import pytest
from pysteps.utils import conversion
from pysteps.xarray_helpers import convert_input_to_xarray_dataset

from pysteps_nwp_importers.importer_bom_nwp import import_bom_nwp
from pysteps_nwp_importers.importer_dwd_nwp import import_dwd_nwp, unstructured2regular
from pysteps_nwp_importers.importer_knmi_nwp import import_knmi_nwp
from pysteps_nwp_importers.importer_rmi_nwp import import_rmi_nwp
from pysteps_nwp_importers.tests.download_test_data import download_test_data

pytest.importorskip("netCDF4")

download_test_data()
DATA_DIR = Path(__file__).parent / "data"

THRESHOLD_TOLERANCE = 0.01
TOLERANCE = 0.0001


def _times(start, stop, step_minutes):
    """Regularly spaced valid times from start to stop (both included)."""
    step = np.timedelta64(step_minutes, "m")
    return np.arange(np.datetime64(start), np.datetime64(stop) + step, step).astype(
        "datetime64[ns]"
    )


# x and y: (first value, last value, stepsize), in cartesian_unit
EXPECTED = dict(
    rmi=dict(
        dims=("time", "y", "x"),
        shape=(24, 564, 564),
        projection=(
            "+proj=lcc +lon_0=4.55 +lat_1=50.8 +lat_2=50.8 "
            "+a=6371229 +es=0 +lat_0=50.8 +x_0=365950 +y_0=-365950.000000001"
        ),
        institution="Royal Meteorological Institute of Belgium",
        units="mm",
        accutime=5,
        zerovalue=0.0,
        threshold=0.0,
        cartesian_unit="m",
        x=(0.0, 731900.0, 1300.0),
        y=(0.0, -731900.0, -1300.0),
        times=_times("2021-07-04T16:05", "2021-07-04T18:00", 5),
    ),
    bom=dict(
        dims=("time", "y", "x"),
        # The accumulated rainfall is disaggregated, which drops the first time step
        shape=(144, 512, 512),
        projection=(
            "+proj=aea  +lon_0=153.240 +lat_0=-27.718 +lat_1=-26.200 +lat_2=-29.300"
        ),
        institution="Commonwealth of Australia, Bureau of Meteorology",
        units="mm",
        accutime=10,
        zerovalue=0.0,
        threshold=0.0,
        cartesian_unit="m",
        x=(-127750.0, 127750.0, 500.0),
        y=(127750.0, -127750.0, -500.0),
        times=_times("2020-10-31T00:10", "2020-11-01T00:00", 10),
    ),
    knmi=dict(
        dims=("time", "y", "x"),
        shape=(49, 300, 300),
        projection="+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs",
        institution="  Royal Netherlands Meteorological Institute (KNMI)  ",
        units="mm",
        accutime=60,
        zerovalue=0.0,
        threshold=0.0,
        cartesian_unit="degrees_east",
        x=(0.0, 11.063, 0.037),
        y=(49.0, 55.877, 0.023),
        times=_times("2018-09-05T06:00", "2018-09-07T06:00", 60),
    ),
    dwd=dict(
        dims=("ens_number", "time", "cell"),
        shape=(20, 13, 542040),
        projection=(
            "+a=6378137.0 +b=6356752.0 +proj=stere +lat_ts=60.0 +lat_0=90.0 +lon_0=10.0"
        ),
        institution="edzw",
        units="mm",
        accutime=5,
        zerovalue=0.0,
        threshold=0.0,
        ens_number=np.arange(1, 21),
        times=_times("2025-06-04T17:00", "2025-06-04T18:00", 5),
    ),
)


def _import_dwd():
    pytest.importorskip("pygrib")
    filename = str(DATA_DIR / "dwd/20250604_1600_PR_GSP_060_120.grib2")
    kwargs = {
        "varname": "lsprate",
        "grid_file_path": str(DATA_DIR / "grid_files/icon_grid_0047_R19B07_L.nc"),
    }
    # The GRIB short name depends on the installed GRIB tables
    try:
        return import_dwd_nwp(filename, **kwargs)
    except OSError:
        kwargs["varname"] = "PR_GSP"
        return import_dwd_nwp(filename, **kwargs)


@pytest.fixture(scope="module")
def dwd_dataset():
    return _import_dwd()


@pytest.fixture(scope="module", params=list(EXPECTED))
def imported_data(request):
    source = request.param
    if source == "rmi":
        dataset = import_rmi_nwp(str(DATA_DIR / "rmi/ao13_2021070412_native_5min.nc"))
    elif source == "bom":
        dataset = import_bom_nwp(str(DATA_DIR / "bom/20201031_0000_regrid_short.nc"))
    elif source == "knmi":
        dataset = import_knmi_nwp(
            str(DATA_DIR / "knmi/20180905_0600_Pforecast_Harmonie.nc")
        )
    else:
        dataset = request.getfixturevalue("dwd_dataset")
    return dataset, EXPECTED[source]


class Test_Importer:
    def test_precip_variable_is_correct(self, imported_data):
        dataset, expected = imported_data
        precip_var = dataset.attrs["precip_var"]
        assert precip_var == "precip_accum"
        assert dataset[precip_var].dims == expected["dims"]
        assert dataset[precip_var].shape == expected["shape"]

    def test_global_attributes_are_correct(self, imported_data):
        dataset, expected = imported_data
        assert dataset.attrs["projection"] == expected["projection"]
        assert dataset.attrs["institution"] == expected["institution"]

    def test_precip_attributes_are_correct(self, imported_data):
        dataset, expected = imported_data
        attrs = dataset[dataset.attrs["precip_var"]].attrs
        assert attrs["units"] == expected["units"]
        assert attrs["accutime"] == expected["accutime"]
        assert attrs["zerovalue"] == pytest.approx(expected["zerovalue"], abs=TOLERANCE)
        assert attrs["threshold"] == pytest.approx(
            expected["threshold"], abs=THRESHOLD_TOLERANCE
        )
        # The data is not transformed: the transform attribute should be absent
        assert "transform" not in attrs

    def test_time_coordinate_is_correct(self, imported_data):
        dataset, expected = imported_data
        np.testing.assert_array_equal(dataset["time"].values, expected["times"])
        step = expected["times"][1] - expected["times"][0]
        assert dataset["time"].attrs["stepsize"] == step / np.timedelta64(1, "s")

    def test_spatial_coordinates_are_correct(self, imported_data):
        dataset, expected = imported_data
        if "cell" in dataset.dims:
            assert dataset["lon"].dims == ("cell",)
            assert dataset["lat"].dims == ("cell",)
            assert dataset["lon"].attrs["units"] == "degrees_east"
            assert dataset["lat"].attrs["units"] == "degrees_north"
            return
        for coord in ("x", "y"):
            first, last, stepsize = expected[coord]
            values = dataset[coord].values
            assert values[0] == pytest.approx(first, abs=TOLERANCE)
            assert values[-1] == pytest.approx(last, abs=TOLERANCE)
            assert dataset[coord].attrs["stepsize"] == pytest.approx(
                stepsize, rel=TOLERANCE
            )
            assert dataset[coord].attrs["units"] == expected["cartesian_unit"]
        assert dataset["lon"].dims == ("y", "x")
        assert dataset["lat"].dims == ("y", "x")

    def test_ens_number_coordinate_is_correct(self, imported_data):
        dataset, expected = imported_data
        if "ens_number" not in expected:
            assert "ens_number" not in dataset.dims
            return
        np.testing.assert_array_equal(
            dataset["ens_number"].values, expected["ens_number"]
        )

    def test_dataset_is_usable_by_pysteps(self, imported_data, tmp_path):
        dataset, _ = imported_data
        subset = dataset.isel(time=slice(0, 2))
        if "ens_number" in subset.dims:
            subset = subset.isel(ens_number=slice(0, 2))

        dataset_mmh = conversion.to_rainrate(subset)
        precip_var = dataset_mmh.attrs["precip_var"]
        assert precip_var == "precip_intensity"
        assert dataset_mmh[precip_var].attrs["units"] == "mm/h"

        # All the attributes can be serialized (e.g. no None values)
        subset.to_netcdf(tmp_path / "dataset.nc")


def _destination_dataset():
    """Dataset on a 10 km version of the DWD radar composite grid."""
    metadata = {
        "projection": (
            "+proj=stere +lat_0=90 +lat_ts=60 +lon_0=10 +a=6378137 "
            "+b=6356752.3142451802 +no_defs +x_0=543196.83521776402 "
            "+y_0=3622588.8619310018 +units=m"
        ),
        "x1": -500.0,
        "y1": -1199500.0,
        "x2": 1099500.0,
        "y2": 500.0,
        "cartesian_unit": "m",
        "yorigin": "upper",
        "institution": "ORG:78,CTY:616,CMT:Deutscher Wetterdienst radolan@dwd.de",
        "accutime": 5.0,
        "unit": "mm/h",
        "zerovalue": 0.0,
        "threshold": 0.12,
    }
    return convert_input_to_xarray_dataset(
        np.zeros((1, 120, 110)),
        None,
        metadata,
        startdate=datetime(2025, 6, 4, 17, 0),
        timestep=300,
    )


def test_unstructured2regular(dwd_dataset):
    dataset_dst = _destination_dataset()

    dataset_rprj = unstructured2regular(dwd_dataset, dataset_dst)

    precip_var = dwd_dataset.attrs["precip_var"]
    assert dataset_rprj.attrs["precip_var"] == precip_var
    precip_rprj = dataset_rprj[precip_var]
    assert precip_rprj.dims == ("ens_number", "time", "y", "x")
    assert precip_rprj.shape == (20, 13, 120, 110)

    # The grid is the one of the destination dataset
    assert dataset_rprj.attrs["projection"] == dataset_dst.attrs["projection"]
    for coord in ("x", "y", "lon", "lat"):
        np.testing.assert_array_equal(
            dataset_rprj[coord].values, dataset_dst[coord].values
        )
        assert dataset_rprj[coord].attrs == dataset_dst[coord].attrs

    # The forecast times, members and metadata are the ones of the source dataset
    for coord in ("time", "ens_number"):
        np.testing.assert_array_equal(
            dataset_rprj[coord].values, dwd_dataset[coord].values
        )
    assert dataset_rprj.attrs["institution"] == dwd_dataset.attrs["institution"]
    for key in ("units", "accutime", "threshold", "zerovalue"):
        assert precip_rprj.attrs[key] == dwd_dataset[precip_var].attrs[key]

    # Every destination pixel gets the value of the nearest source grid cell
    pr = pyproj.Proj(dataset_dst.attrs["projection"])
    x_src, y_src = pr(dwd_dataset["lon"].values, dwd_dataset["lat"].values)
    for i, j in [(0, 0), (60, 55), (119, 109)]:
        x_dst = dataset_dst["x"].values[j]
        y_dst = dataset_dst["y"].values[i]
        nearest = np.argmin((x_src - x_dst) ** 2 + (y_src - y_dst) ** 2)
        np.testing.assert_array_equal(
            precip_rprj.values[:, :, i, j],
            dwd_dataset[precip_var].values[:, :, nearest],
        )

    # The reprojected dataset can be used by pysteps
    conversion.to_rainrate(dataset_rprj.isel(ens_number=0))


def test_unstructured2regular_requires_unstructured_source():
    dataset_dst = _destination_dataset()
    with pytest.raises(ValueError, match="unstructured grid"):
        unstructured2regular(dataset_dst, dataset_dst)
