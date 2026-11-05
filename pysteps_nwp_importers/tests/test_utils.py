import numpy as np
import pytest

from pysteps_nwp_importers._utils import (
    disaggregate_accumulation,
    get_timestep_seconds,
    to_pysteps_dataset,
)

TIMES = np.array(
    ["2021-07-04T12:00", "2021-07-04T12:05", "2021-07-04T12:10"],
    dtype="datetime64[ns]",
)

METADATA = dict(
    projection="+proj=lcc +lon_0=4.55 +lat_1=50.8 +lat_2=50.8 +lat_0=50.8",
    institution="test",
    unit="mm",
    accutime=5,
    threshold=0.1,
    zerovalue=0.0,
    transform=None,
    cartesian_unit="m",
)


def test_get_timestep_seconds():
    assert get_timestep_seconds(TIMES) == 300


@pytest.mark.parametrize(
    "times",
    [
        TIMES[:1],
        np.array(
            ["2021-07-04T12:00", "2021-07-04T12:05", "2021-07-04T12:15"],
            dtype="datetime64[ns]",
        ),
    ],
)
def test_get_timestep_seconds_requires_regular_times(times):
    with pytest.raises(ValueError):
        get_timestep_seconds(times)


def test_disaggregate_accumulation():
    accumulated = np.array([[1.0, 2.0], [1.5, 2.0], [3.0, 4.0]])
    precip, times = disaggregate_accumulation(accumulated, TIMES)
    np.testing.assert_array_equal(precip, [[0.5, 0.0], [1.5, 2.0]])
    np.testing.assert_array_equal(times, TIMES[1:])


@pytest.mark.parametrize("y_descending", [True, False])
def test_to_pysteps_dataset(y_descending):
    x = np.array([500.0, 1500.0, 2500.0, 3500.0])
    y = np.array([-500.0, -1500.0, -2500.0])
    if not y_descending:
        y = y[::-1]
    precip = np.random.default_rng(42).random((3, 3, 4))

    dataset = to_pysteps_dataset(precip, x, y, TIMES, METADATA)

    precip_var = dataset.attrs["precip_var"]
    np.testing.assert_array_equal(dataset[precip_var].values, precip)
    np.testing.assert_allclose(dataset["x"].values, x)
    np.testing.assert_allclose(dataset["y"].values, y)
    assert dataset["x"].attrs["stepsize"] == pytest.approx(1000.0)
    assert dataset["y"].attrs["stepsize"] == pytest.approx(
        -1000.0 if y_descending else 1000.0
    )
    np.testing.assert_array_equal(dataset["time"].values, TIMES)
    assert dataset["time"].attrs["stepsize"] == 300
    # Metadata set to None is left out of the dataset
    assert "transform" not in dataset[precip_var].attrs
    assert dataset[precip_var].attrs["accutime"] == 5


def test_to_pysteps_dataset_with_descending_x():
    x = np.array([2500.0, 1500.0, 500.0])
    y = np.array([500.0, 1500.0])
    precip = np.arange(12.0).reshape((2, 2, 3))

    dataset = to_pysteps_dataset(precip, x, y, TIMES[:2], METADATA)

    np.testing.assert_allclose(dataset["x"].values, x[::-1])
    np.testing.assert_array_equal(
        dataset[dataset.attrs["precip_var"]].values, precip[..., ::-1]
    )


def test_to_pysteps_dataset_with_ensemble():
    x = np.array([500.0, 1500.0])
    y = np.array([500.0, 1500.0])
    precip = np.zeros((2, 3, 2, 2))

    dataset = to_pysteps_dataset(precip, x, y, TIMES, METADATA, ens_number=[3, 7])

    assert dataset[dataset.attrs["precip_var"]].dims == ("ens_number", "time", "y", "x")
    np.testing.assert_array_equal(dataset["ens_number"].values, [3, 7])
    assert dataset["ens_number"].attrs["standard_name"] == "realization"


def test_to_pysteps_dataset_requires_supported_unit():
    x = np.array([500.0, 1500.0])
    y = np.array([500.0, 1500.0])
    with pytest.raises(ValueError, match="Unsupported precipitation unit"):
        to_pysteps_dataset(
            np.zeros((3, 2, 2)), x, y, TIMES, {**METADATA, "unit": "kg m-2 s-1"}
        )
