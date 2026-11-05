"""
pysteps_nwp_importers._utils
============================

Helpers shared by the NWP importers to build xarray datasets that follow the
pysteps data model (see :py:mod:`pysteps.io.importers`).

pysteps is imported inside the functions on purpose: importing pysteps loads
the importer plugins (entry points), so importing it while the modules of this
package are being initialized would be circular when pysteps_nwp_importers is
imported before pysteps.
"""

import datetime

import numpy as np
import xarray as xr

# Unit spellings found in NWP files that correspond to the pysteps "mm" unit.
_MM_UNITS = ("kg m-2", "kg m**-2", "mm")

TIME_ATTRS = {"long_name": "forecast time"}
ENS_NUMBER_ATTRS = {
    "long_name": "ensemble member",
    "standard_name": "realization",
    "units": "",
}


def normalize_unit(unit):
    """Map the precipitation unit of an NWP file onto a pysteps unit."""
    if unit in _MM_UNITS:
        return "mm"
    return unit


def get_threshold_value(precip):
    """
    Get the rain/no rain threshold with the same unit, transformation and
    accutime of the data.
    If all the values are NaNs, the returned value is `np.nan`.
    Otherwise, np.min(precip[precip > precip.min()]) is returned.

    Returns
    -------
    threshold: float
    """
    valid_mask = np.isfinite(precip)
    if valid_mask.any():
        _precip = precip[valid_mask]
        min_precip = _precip.min()
        above_min_mask = _precip > min_precip
        if above_min_mask.any():
            return np.min(_precip[above_min_mask])
        else:
            return min_precip
    else:
        return np.nan


def get_timestep_seconds(times):
    """
    Return the (regular) spacing in seconds of a series of valid times.

    The pysteps data model requires the time dimension to be regularly spaced.
    """
    times = np.asarray(times, dtype="datetime64[s]")
    if times.size < 2:
        raise ValueError(
            "At least two time steps are needed to determine the time step of the "
            "NWP forecast"
        )
    steps = np.unique(np.diff(times))
    if steps.size != 1:
        raise ValueError(
            "The time steps of the NWP forecast are not regularly spaced: "
            f"{steps.astype('timedelta64[m]')}"
        )
    return int(steps[0] / np.timedelta64(1, "s"))


def disaggregate_accumulation(precip, times, time_axis=0):
    """
    Convert precipitation accumulated since the forecast start into
    accumulations per time step.

    The field at time t becomes the accumulation over (t - 1, t]. The first
    time step has no predecessor and is dropped.
    """
    return np.diff(precip, axis=time_axis), np.asarray(times)[1:]


def time_coordinate(times, timestep):
    """Build a time coordinate following the conventions of pysteps."""
    times = np.asarray(times, dtype="datetime64[ns]")
    startdate = _to_datetime(times[0])
    return (
        ["time"],
        times,
        {**TIME_ATTRS, "stepsize": timestep},
        {"units": f"seconds since {startdate:%Y-%m-%d %H:%M:%S}"},
    )


def to_pysteps_dataset(precip, x, y, times, metadata, ens_number=None):
    """
    Wrap gridded NWP precipitation fields into a pysteps dataset.

    Parameters
    ----------
    precip: np.ndarray
        Array of shape (time, y, x) or (ens_number, time, y, x). The rows and
        columns are ordered like `y` and `x`.
    x, y: array-like
        1D arrays with the regularly spaced cell-centre coordinates of the
        columns and rows of `precip`.
    times: array-like
        1D array with the regularly spaced valid times of the fields.
    metadata: dict
        Metadata as described in :py:mod:`pysteps.io.importers`. The grid
        description (x1, x2, y1, y2, yorigin, pixel sizes) is derived from `x`
        and `y`. Keys with a value of None are left out of the dataset.
    ens_number: array-like, optional
        Ensemble member numbers. Only used if `precip` has 4 dimensions.
        Defaults to 1, 2, ..., n.

    Returns
    -------
    dataset: xarray.Dataset
        Dataset following the pysteps data model.
    """
    from pysteps.xarray_helpers import convert_input_to_xarray_dataset

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    # The pysteps data model expects x to increase along the columns.
    if x[0] > x[-1]:
        x = x[::-1]
        precip = precip[..., ::-1]

    xpixelsize = _get_pixelsize(x, "x")
    ypixelsize = _get_pixelsize(y, "y")

    metadata = {key: value for key, value in metadata.items() if value is not None}
    _check_unit(metadata)
    # x1, x2, y1 and y2 are the outer edges of the grid, not the cell centres.
    # The pixel sizes are left out on purpose: pysteps then derives them from
    # the grid edges and the shape of the data.
    metadata.update(
        x1=x.min() - 0.5 * xpixelsize,
        x2=x.max() + 0.5 * xpixelsize,
        y1=y.min() - 0.5 * ypixelsize,
        y2=y.max() + 0.5 * ypixelsize,
        yorigin="upper" if y[0] > y[-1] else "lower",
    )
    for key in ("xpixelsize", "ypixelsize"):
        metadata.pop(key, None)

    times = np.asarray(times, dtype="datetime64[ns]")
    dataset = convert_input_to_xarray_dataset(
        precip,
        None,
        metadata,
        startdate=_to_datetime(times[0]),
        timestep=get_timestep_seconds(times),
    )

    if ens_number is not None and "ens_number" in dataset.dims:
        dataset = dataset.assign_coords(
            ens_number=(
                "ens_number",
                np.asarray(ens_number),
                dataset["ens_number"].attrs,
            )
        )

    return dataset


def to_pysteps_unstructured_dataset(precip, lon, lat, times, ens_number, metadata):
    """
    Wrap NWP precipitation fields on an unstructured grid into a dataset that
    follows the pysteps data model as closely as possible.

    `precip` has the dimensions (ens_number, time, cell). The dataset has no x
    and y coordinates. Instead, the location of every grid cell is given by the
    lon and lat coordinates along the "cell" dimension.
    """
    from pysteps.xarray_helpers import cf_parameters_from_unit

    metadata = {key: value for key, value in metadata.items() if value is not None}
    _check_unit(metadata)
    var_name, var_attrs = cf_parameters_from_unit(metadata["unit"])
    for key in ("transform", "accutime", "zr_a", "zr_b", "threshold", "zerovalue"):
        if key in metadata:
            var_attrs[key] = metadata[key]

    return xr.Dataset(
        data_vars={var_name: (["ens_number", "time", "cell"], precip, var_attrs)},
        coords={
            "ens_number": (["ens_number"], np.asarray(ens_number), ENS_NUMBER_ATTRS),
            "time": time_coordinate(times, get_timestep_seconds(times)),
            "lon": (
                ["cell"],
                np.asarray(lon),
                {
                    "long_name": "longitude coordinate",
                    "standard_name": "longitude",
                    "units": "degrees_east",
                },
            ),
            "lat": (
                ["cell"],
                np.asarray(lat),
                {
                    "long_name": "latitude coordinate",
                    "standard_name": "latitude",
                    "units": "degrees_north",
                },
            ),
        },
        attrs={
            "Conventions": "CF-1.7",
            "institution": metadata["institution"],
            "projection": metadata["projection"],
            "precip_var": var_name,
        },
    )


def _check_unit(metadata):
    unit = metadata.get("unit")
    if unit not in ("mm", "mm/h", "dBZ"):
        raise ValueError(
            f"Unsupported precipitation unit {unit!r}. "
            "The pysteps data model supports 'mm', 'mm/h' and 'dBZ'."
        )


def _get_pixelsize(coord, name):
    if coord.size < 2:
        raise ValueError(f"The {name} coordinate needs at least two values")
    steps = np.diff(coord)
    if not np.allclose(steps, steps[0], rtol=1e-6, atol=0.0):
        raise ValueError(f"The {name} coordinate is not regularly spaced")
    return abs(float(np.mean(steps)))


def _to_datetime(time):
    """Convert a numpy datetime64 into a datetime.datetime."""
    return np.datetime64(time, "us").astype(datetime.datetime)
