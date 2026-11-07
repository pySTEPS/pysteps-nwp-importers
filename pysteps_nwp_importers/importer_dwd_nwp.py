"""
pysteps_nwp_importers.importer_dwd_nwp
======================================

Module to import the DWD ICON-RUC NWP forecasts. The importer returns an xarray
dataset with the desired precipitation related variable per ensemble member and
time step, following the pysteps data model described in
:py:mod:`pysteps.io.importers` as closely as possible.

The structure of the dataset depends on the grid of the variable, since
rainfall related variables are available only on an unstructured triangular
grid whereas EMVORADO-simulated reflectivities are available on a rotated
lat-lon grid:

- On the unstructured grid (rain rate, acc. precipitation, etc.), the
  precipitation variable has the dimensions (ens_number, time, cell). The
  location of every grid cell is given by the ``lon`` and ``lat`` coordinates.
  Such a dataset can be reprojected onto a regular grid (for instance the grid
  of a radar composite) with :py:func:`unstructured2regular`, which returns a
  regular pysteps dataset.
- On the rotated lat-lon grid (EMVORADO synthetic reflectivities), the
  precipitation variable has the dimensions (ens_number, time, y, x), with
  regularly spaced x and y coordinates.

In both cases, the metadata is stored as follows:

.. tabularcolumns:: |p{3cm}|L|

+------------------------------+----------------------------------------------+
|       Location               |                Value                         |
+==============================+==============================================+
| ``attrs["projection"]``      | PROJ.4-compatible projection definition      |
+------------------------------+----------------------------------------------+
| ``attrs["institution"]``     | name of the institution who provides the data|
+------------------------------+----------------------------------------------+
| ``attrs["precip_var"]``      | name of the precipitation data variable      |
+------------------------------+----------------------------------------------+
| precip_var ``units``         | the physical unit of the data: 'mm', 'mm/h'  |
|                              | or 'dBZ'                                     |
+------------------------------+----------------------------------------------+
| precip_var ``accutime``      | the accumulation time in minutes of the data |
|                              | (only for accumulated variables)             |
+------------------------------+----------------------------------------------+
| precip_var ``threshold``     | the rain/no rain threshold with the same     |
|                              | unit and accutime of the data                |
+------------------------------+----------------------------------------------+
| precip_var ``zerovalue``     | the value assigned to the no rain pixels with|
|                              | the same unit and accutime of the data       |
+------------------------------+----------------------------------------------+
| time coordinate              | valid times, regularly spaced by ``stepsize``|
|                              | (in seconds)                                 |
+------------------------------+----------------------------------------------+
| ens_number coordinate        | ensemble member (GRIB perturbationNumber, or |
|                              | 0 for a deterministic forecast)              |
+------------------------------+----------------------------------------------+

A comprehensive documentation of the data and the NWP model itself can be test
found at: https://www.dwd.de/SharedDocs/downloads/DE/modelldokumentationen/nwv/
    icon_d2/icon_d2_dbbeschr_aktuell.pdf?view=nasPublication&nn=346850

"""

import numpy as np
import pyproj
import xarray as xr
from xarray.indexes import NDPointIndex

from pysteps_nwp_importers._utils import (
    get_threshold_value,
    get_timestep_seconds,
    normalize_unit,
    to_pysteps_dataset,
    to_pysteps_unstructured_dataset,
)

# GRIB doesn't define a projection for the unstructured grid. This one is used to
# reproject it with unstructured2regular.
UNSTRUCTURED_GRID_PROJECTION = (
    "+a=6378137.0 +b=6356752.0 +proj=stere +lat_ts=60.0 +lat_0=90.0 +lon_0=10.0"
)


def import_dwd_nwp(filename, **kwargs):
    """
    Import a GRIB file containing DWD ICON-D2-RUC NWP precipitation forecasts using
    cfgrib and xarray.

    Parameters
    ----------
    filename: str
        Name of the file to import.

    Other Parameters
    ----------------
    varname: str
        GRIB short name of the desired variable (depends on the installed GRIB tables):
        - DBZCMP_SIM = EMVORADO synthetic reflectivities
        - PR_GSP (lsprate) = grid scale precipitation rate
        - TOT_PREC (tp) = accumulated precipitation since forecast initialization
    grid_file_path: str
        Path to the forecast data associated grid file. Required for variables on
        the unstructured grid.

    Returns
    -------
    dataset: xarray.Dataset
        Dataset containing the precipitation forecasts and the associated metadata
        (see the documentation of :py:mod:`pysteps_nwp_importers.importer_dwd_nwp`).
        Precipitation rates in kg m**-2 s**-1 are converted into accumulations
        per time step (in mm). Accumulated variables, which ICON accumulates since
        the forecast initialization, are disaggregated into accumulations per time
        step, which drops the first time step.
    """

    varname = kwargs.get("varname", "DBZCMP_SIM")
    try:
        ds = xr.open_dataset(
            filename,
            engine="cfgrib",
            backend_kwargs=dict(
                filter_by_keys={"shortName": varname},
                # Don't write an index file next to the GRIB file
                indexpath="",
                read_keys=["radius"],
                values_dtype=np.dtype("float64"),
            ),
        )
    except Exception as e:
        raise IOError(f"File could not be opened, because of: {e}")

    with ds:
        if not ds.data_vars:
            raise IOError("File does not contain the desired precipitation variable")
        (precip,) = ds.data_vars.values()
        precip = precip.load()
        institution = ds.attrs["GRIB_centre"]
    grib_attrs = precip.attrs

    if precip["time"].ndim:
        raise ValueError("File should contain only one forecast init.")

    timestep = get_timestep_seconds(precip["valid_time"].values)

    # Dimensions (ensemble member, step, *grid), with member 0 for a deterministic
    # forecast
    if "number" not in precip.coords:
        precip = precip.assign_coords(number=0)
    if "number" not in precip.dims:
        precip = precip.expand_dims("number")
    precip = precip.transpose("number", "step", ...)

    metadata = dict(
        projection=_get_projection(grib_attrs),
        unit=normalize_unit(grib_attrs.get("GRIB_units")),
        institution=institution,
    )

    # Convert precipitation rates into accumulations per time step
    lrate = metadata["unit"] == "kg m**-2 s**-1"
    if lrate:
        precip = precip * timestep
        metadata["unit"] = "mm"

    # Disaggregate accumulated variables: the field at time t becomes the
    # accumulation over (t - 1, t]. The GRIB packing can make it slightly negative.
    laccum = grib_attrs["GRIB_stepType"] == "accum"
    if laccum:
        precip = precip.diff("step").clip(min=0.0)

    values = precip.values
    valid_times = precip["valid_time"].values
    ens_numbers = precip["number"].values

    # Set threshold and zerovalue of the dataset
    # For synthetic reflectivities no data and noch echo is set in the GRIB to -999 and
    # -99, respectively. To handle these in a more comfortable manner, it is set here
    # to -2 and 2. However, currently hard coded...
    metadata["zerovalue"] = np.nanmin(values) if varname != "DBZCMP_SIM" else -2.0
    metadata["threshold"] = (
        get_threshold_value(values) if varname != "DBZCMP_SIM" else 2.0
    )
    # The accumulated variables (and the precipitation rates, which have been
    # converted above) contain the accumulation per time step.
    metadata["accutime"] = timestep // 60 if (laccum or lrate) else None

    if grib_attrs["GRIB_gridType"] == "unstructured_grid":
        lon, lat = _read_grid_file(kwargs.get("grid_file_path"), precip.sizes["values"])
        return to_pysteps_unstructured_dataset(
            values, lon, lat, valid_times, ens_numbers, metadata
        )

    # Regular or rotated lat/lon grid
    field = precip.isel(number=0, step=0)
    lon, lat = (
        field[name].broadcast_like(field).transpose(*field.dims).values
        for name in ("longitude", "latitude")
    )
    x, y = pyproj.Proj(metadata["projection"])(lon, lat)
    metadata["cartesian_unit"] = "m"
    return to_pysteps_dataset(
        values, x[0], y[:, 0], valid_times, metadata, ens_number=ens_numbers
    )


def unstructured2regular(dataset_src, dataset_dst):
    """
    Reproject NWP data on an unstructured grid onto the regular grid of another
    dataset, using nearest neighbor interpolation.

    Parameters
    ----------
    dataset_src: xarray.Dataset
        Dataset on an unstructured grid, as returned by :py:func:`import_dwd_nwp`.
        Its precipitation variable has a "cell" dimension, along which the ``lon``
        and ``lat`` coordinates give the location of the grid cells.
    dataset_dst: xarray.Dataset
        Dataset following the pysteps data model that defines the destination
        grid, for instance a radar dataset. Its ``x`` and ``y`` coordinates and
        its ``projection`` attribute are used. The x and y coordinates are assumed
        to be expressed in the units of that projection.

    Returns
    -------
    dataset: xarray.Dataset
        Dataset following the pysteps data model, with the precipitation variable
        of `dataset_src` reprojected onto the grid of `dataset_dst`. The
        precipitation variable has the dimensions of `dataset_src`, with the
        "cell" dimension replaced by (y, x), e.g. (ens_number, time, y, x). The
        spatial coordinates and the projection are those of `dataset_dst`.
        Destination grid cells outside of the source domain get the value of the
        nearest source grid cell.
    """

    if "cell" not in dataset_src.dims:
        raise ValueError(
            "dataset_src should be on an unstructured grid with a 'cell' dimension"
        )

    # Location of the source grid cells in the destination projection, with a
    # KD-tree index for nearest neighbour lookups
    x_src, y_src = pyproj.Proj(dataset_dst.attrs["projection"])(
        dataset_src["lon"].values, dataset_src["lat"].values
    )
    dataset = (
        dataset_src.drop_vars(["lon", "lat"])
        .assign_coords(x_src=("cell", x_src), y_src=("cell", y_src))
        .set_xindex(["x_src", "y_src"], NDPointIndex)
    )

    # Select the nearest source grid cell of every destination grid cell
    x_dst, y_dst = xr.broadcast(dataset_dst["x"], dataset_dst["y"])
    dataset = dataset.sel(x_src=x_dst, y_src=y_dst, method="nearest")
    dataset = dataset.drop_vars(["x_src", "y_src"]).transpose(..., "y", "x")

    # Spatial coordinates (x, y, lon, lat and the grid mapping) and projection
    # of the destination
    dataset = dataset.assign_coords(
        {
            name: coord
            for name, coord in dataset_dst.coords.items()
            if set(coord.dims) <= {"y", "x"}
        }
    )
    precip_var = dataset.attrs["precip_var"]
    precip_attrs = {
        key: value
        for key, value in dataset[precip_var].attrs.items()
        if key != "grid_mapping"
    }
    dst_precip_var = dataset_dst.attrs.get("precip_var")
    if (
        dst_precip_var in dataset_dst
        and "grid_mapping" in dataset_dst[dst_precip_var].attrs
    ):
        precip_attrs["grid_mapping"] = dataset_dst[dst_precip_var].attrs["grid_mapping"]
    dataset[precip_var].attrs = precip_attrs

    return dataset.assign_attrs(projection=dataset_dst.attrs["projection"])


def _get_projection(attrs):
    """
    Get the PROJ.4 definition of the grid of a variable opened with cfgrib.

    GRIB doesn't define a projection for the unstructured grid, so a hard coded one
    is returned for it.
    """
    grid_type = attrs["GRIB_gridType"]
    if grid_type == "unstructured_grid":
        return UNSTRUCTURED_GRID_PROJECTION
    if grid_type not in ("regular_ll", "rotated_ll"):
        raise ValueError(f"Unsupported GRIB grid type: {grid_type}")
    if "GRIB_radius" not in attrs:
        raise ValueError("Only grids on a spherical earth are supported")
    earth = f"+a={attrs['GRIB_radius']} +b={attrs['GRIB_radius']}"
    if grid_type == "regular_ll":
        return f"{earth} +proj=longlat"
    return (
        f"{earth} +proj=ob_tran +o_proj=longlat"
        f" +o_lat_p={-attrs['GRIB_latitudeOfSouthernPoleInDegrees']}"
        f" +o_lon_p={attrs['GRIB_angleOfRotationInDegrees']}"
        f" +lon_0={attrs['GRIB_longitudeOfSouthernPoleInDegrees']}"
    )


def _read_grid_file(grid_file_path, n_cells):
    """
    Reads the coordinates of the unstructured triangular grid
    from the grid file

    Parameters
    ----------
    grid_file_path: str
        Path to the forecast data associated grid file
    n_cells: int
        Number of grid cells of the forecast data

    Returns
    -------
    lon, lat: np.ndarray
        Longitude and latitude (in degrees) of the triangle centers
    """
    if not grid_file_path:
        raise ValueError(
            "grid_file_path is required to import DWD NWP data on the "
            "unstructured grid"
        )
    with xr.open_dataset(grid_file_path) as ds:
        lon, lat = np.rad2deg(ds["clon"].values), np.rad2deg(ds["clat"].values)
    if lon.size != n_cells:
        raise ValueError(
            f"The grid file {grid_file_path} has {lon.size} cells, but the "
            f"GRIB file has {n_cells} data points"
        )
    return lon, lat
