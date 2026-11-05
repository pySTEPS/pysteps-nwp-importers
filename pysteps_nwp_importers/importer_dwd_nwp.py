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

import datetime

import netCDF4 as nc
import numpy as np
import xarray as xr
from scipy.spatial import KDTree

from pysteps_nwp_importers._utils import (
    disaggregate_accumulation,
    get_threshold_value,
    get_timestep_seconds,
    normalize_unit,
    to_pysteps_dataset,
    to_pysteps_unstructured_dataset,
)

try:
    import pygrib

    PYGRIB_IMPORTED = True
except ImportError:
    PYGRIB_IMPORTED = False

try:
    import pyproj

    PYPROJ_IMPORTED = True
except ImportError:
    PYPROJ_IMPORTED = False

from pysteps_nwp_importers.exceptions import MissingOptionalDependency


def import_dwd_nwp(filename, **kwargs):
    """
    Import a GRIB file containing DWD ICON-D2-RUC NWP precipitation forecasts using
    pygrib and xarray.

    Parameters
    ----------
    filename: str
        Name of the file to import.

    Other Parameters
    ----------------
    varname: str
        GRIB short name of the desired variable (depends on the installed GRIB tables):
        - DBZCMP_SIM = EMVORADO synthetic reflectivities
        - PR_GSP = grid scale precipitation rate
        - TOT_PREC = accumulated precipitation since forecast initialization
    grid_file_path: str
        Path to the forecast data associated grid file. Required for variables on
        the unstructured grid.

    Returns
    -------
    dataset: xarray.Dataset
        Dataset containing the precipitation forecasts and the associated metadata
        (see the documentation of :py:mod:`pysteps_nwp_importers.importer_dwd_nwp`).
        Precipitation rates in kg m**-2 s**-1 are converted into accumulations
        per time step (in mm). Precipitation accumulated since the forecast
        initialization (TOT_* variables) is disaggregated into accumulations per
        time step, which drops the first time step.
    """

    if not PYGRIB_IMPORTED:
        raise MissingOptionalDependency(
            "pygrib package is required to import DWD NWP precipitation "
            "forecasts but it is not installed"
        )

    if not PYPROJ_IMPORTED:
        raise MissingOptionalDependency(
            "pyproj package is required to import DWD NWP precipitation "
            "forecasts but it is not installed"
        )

    # Try to open file with pygrib
    try:
        grib_file = pygrib.open(filename)
    except Exception as e:
        raise IOError("File could not be opened, because of: " f"{e}")

    # Read complete grib file
    grib_msgs = grib_file.read()
    grib_file.close()

    # Check whether the file contains any processible precipitation variable
    varname = kwargs.get("varname", "DBZCMP_SIM")
    data_varnames = np.unique([grib_msg["shortName"] for grib_msg in grib_msgs])

    # Raise error if file doesn't contain the desired variable
    if not varname in data_varnames:
        raise IOError("File does not contain the desired precipitation variable")

    # Raise error if file contains more than one variable
    assert (
        len(data_varnames) == 1
    ), "File should contain only one precipitation variable."

    # Check the initialization time
    reference_time = np.unique([grib_msg.analDate for grib_msg in grib_msgs])
    # Raise error if file contains more than one forecast init
    assert len(reference_time) == 1, "File should contain only one forecast init."

    # Check whether the file contains an accumulated variable
    laccum = (
        grib_msgs[0].has_key("typeOfStatisticalProcessing")
        and grib_msgs[0]["typeOfStatisticalProcessing"] == 1
    )
    valid_times = [_get_valid_time(grib_msg, laccum) for grib_msg in grib_msgs]

    # Get all ensemble members that the dataset contains
    ens_numbers = np.unique([_get_ens_number(grib_msg) for grib_msg in grib_msgs])

    # Check whether each ensemble member has the same number of forecast times
    # Currently, only the number is compared and not the individual forecast times
    # themselves.
    assert len(valid_times) / len(ens_numbers) == len(
        np.unique(valid_times)
    ), "No. of time stamps not equal between ensemble members."
    valid_times = np.unique(valid_times)

    # Get the temporal resolution
    timestep = get_timestep_seconds(np.array(valid_times, dtype="datetime64[s]"))
    temp_res = timestep // 60

    # Get the grid and the metadata of the variable
    grid, metadata = _import_dwd_nwp_geodata(grib_msgs[0], **kwargs)

    # Fill the data array with values of the grib messages by ensemble member and
    # forecast time
    ens_index = {ens_number: i for i, ens_number in enumerate(ens_numbers)}
    time_index = {valid_time: i for i, valid_time in enumerate(valid_times)}
    precip = np.full(
        (len(ens_numbers), len(valid_times)) + grid["shape"], np.nan, dtype=float
    )
    for grib_msg in grib_msgs:
        i_ens = ens_index[_get_ens_number(grib_msg)]
        i_time = time_index[_get_valid_time(grib_msg, laccum)]
        precip[i_ens, i_time] = grib_msg["values"]

    # The no data is set to 9999.0, change it to nan.
    precip[~(precip < 9999)] = np.nan

    # Convert precipitation rates into accumulations per time step
    lrate = metadata["unit"] == "kg m**-2 s**-1"
    if lrate:
        precip *= timestep
        metadata["unit"] = "mm"

    # Disaggregate variables that are accumulated since forecast initialization
    if laccum and "TOT_" in varname:
        precip, valid_times = disaggregate_accumulation(
            precip, valid_times, time_axis=1
        )

    # Set threshold and zerovalue of the dataset
    # For synthetic reflectivities no data and noch echo is set in the GRIB to -999 and
    # -99, respectively. To handle these in a more comfortable manner, it is set here
    # to -2 and 2. However, currently hard coded...
    metadata["zerovalue"] = np.nanmin(precip) if varname != "DBZCMP_SIM" else -2.0
    metadata["threshold"] = (
        get_threshold_value(precip) if varname != "DBZCMP_SIM" else 2.0
    )
    # The accumulated variables (and the precipitation rates, which have been
    # converted above) contain the accumulation per time step.
    metadata["accutime"] = temp_res if (laccum or lrate) else None

    valid_times = np.array(valid_times, dtype="datetime64[ns]")
    if grid["type"] == "unstructured":
        return to_pysteps_unstructured_dataset(
            precip, grid["lon"], grid["lat"], valid_times, ens_numbers, metadata
        )
    return to_pysteps_dataset(
        precip, grid["x"], grid["y"], valid_times, metadata, ens_number=ens_numbers
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

    if not PYPROJ_IMPORTED:
        raise MissingOptionalDependency(
            "pyproj package is required to reproject DWD's NWP data"
            "but it is not installed"
        )

    if not "cell" in dataset_src.dims:
        raise ValueError(
            "dataset_src should be on an unstructured grid with a 'cell' dimension"
        )
    if not "lon" in dataset_src.coords:
        raise KeyError("Longitude (lon) of the cells is missing in dataset_src")
    if not "lat" in dataset_src.coords:
        raise KeyError("Latitude (lat) of the cells is missing in dataset_src")

    # Get cartesian coordinates of destination grid
    xx_dst, yy_dst = np.meshgrid(dataset_dst["x"].values, dataset_dst["y"].values)

    # Get the location of the source grid cells in the destination projection
    pr = pyproj.Proj(dataset_dst.attrs["projection"])
    x_src, y_src = pr(dataset_src["lon"].values, dataset_src["lat"].values)

    # Nearest neighbor interpolation of x-y pairs
    _, ic_out = KDTree(np.column_stack((x_src, y_src))).query(
        np.column_stack((xx_dst.ravel(), yy_dst.ravel()))
    )
    ic_out = ic_out.reshape(xx_dst.shape)

    # Apply interpolation on all time steps and ensemble members
    precip_var = dataset_src.attrs["precip_var"]
    da_src = dataset_src[precip_var].transpose(..., "cell")
    dims = [dim for dim in da_src.dims if dim != "cell"] + ["y", "x"]
    precip_rprj = da_src.values[..., ic_out]

    precip_attrs = {
        key: value for key, value in da_src.attrs.items() if key != "grid_mapping"
    }
    dst_precip_var = dataset_dst.attrs.get("precip_var")
    if (
        dst_precip_var in dataset_dst
        and "grid_mapping" in dataset_dst[dst_precip_var].attrs
    ):
        precip_attrs["grid_mapping"] = dataset_dst[dst_precip_var].attrs["grid_mapping"]

    # Non-spatial coordinates (time, ens_number) of the source and spatial
    # coordinates (x, y, lon, lat and the grid mapping) of the destination
    coords = {
        name: coord
        for name, coord in dataset_src.coords.items()
        if not "cell" in coord.dims
    }
    for name, coord in dataset_dst.coords.items():
        if coord.dims and set(coord.dims) <= {"y", "x"}:
            coords[name] = coord
        elif not coord.dims and "grid_mapping_name" in coord.attrs:
            coords[name] = coord

    return xr.Dataset(
        data_vars={precip_var: (dims, precip_rprj, precip_attrs)},
        coords=coords,
        attrs={**dataset_src.attrs, "projection": dataset_dst.attrs["projection"]},
    )


def _import_dwd_nwp_geodata(grib_msg, **kwargs):
    """
    Get all necessary metadata for further processing from data the GRIB file contains.

    Parameters
    ----------
    grib_msg: Grib message object
        Single grib message from which metadata is to be extracted

    Other parameters
    ----------------
    grid_file_path: str
        Path to the forecast data associated grid file

    Returns
    -------
    tuple
        A tuple containing the following:
        - grid : dict
            The type of grid ("regular" or "unstructured"), the shape of a single
            field, and the coordinates of the grid (x and y for a regular grid,
            lon and lat for an unstructured grid).
        - metadata : dict
            Associated metadata (map projection, unit, etc.; see doc of
            pysteps_nwp_importers.importer_dwd_nwp).
    """

    # Set the unit of the desired variable
    units = None
    if "units" in grib_msg.keys():
        units = normalize_unit(grib_msg["units"])

    # For the rotated lat/lon grid the projection definition is extracted from
    # pygrib.proj_params. For the unstructured grid, it is unfortunately hard coded,
    # since proj_params does not support this kind of grids.
    proj_params = grib_msg.projparams
    if proj_params is None:
        proj_def = (
            "+a=6378137.0 +b=6356752.0 +proj=stere +lat_ts=60.0 +lat_0=90.0 +lon_0=10.0"
        )
    else:
        proj_def = " ".join([f"+{key}={value} " for key, value in proj_params.items()])

    metadata = dict()

    # Get the coordinates of a rotated lat/lon grid
    if grib_msg.has_key("Nj"):
        # Get geographical coordinates from grib message
        _, lat, lon = grib_msg.data()
        # Get projection and corresponding carthesian coordinates
        proj = pyproj.Proj(proj_params)
        x, y = proj(lon, lat)
        grid = dict(
            type="regular",
            shape=(grib_msg["Nj"], grib_msg["Ni"]),
            x=x[0],
            y=y[:, 0],
        )
        metadata["cartesian_unit"] = "m"

    # Get the coordinates of an unstructured triangular grid
    else:
        # Get geographical coordinates of triangle centers from grid file
        grid_file_path = kwargs.get("grid_file_path")
        if not grid_file_path:
            raise ValueError(
                "grid_file_path is required to import DWD NWP data on the "
                "unstructured grid"
            )
        clon, clat = _read_grid_file(grid_file_path)
        if clon.size != grib_msg["numberOfDataPoints"]:
            raise ValueError(
                f"The grid file {grid_file_path} has {clon.size} cells, but the "
                f"GRIB file has {grib_msg['numberOfDataPoints']} data points"
            )
        grid = dict(
            type="unstructured",
            shape=(grib_msg["numberOfDataPoints"],),
            lon=clon,
            lat=clat,
        )

    # Fill metadata dictionary with projection definition, unit of the precipitation
    # variable, transformation as well as the originating institution
    metadata["projection"] = proj_def
    metadata["unit"] = units
    metadata["institution"] = grib_msg["centre"]

    return grid, metadata


def _get_ens_number(grib_msg):
    """Get the ensemble member of a GRIB message (0 for a deterministic run)."""
    if grib_msg.has_key("perturbationNumber"):
        return int(grib_msg["perturbationNumber"])
    return 0


def _get_valid_time(grib_msg, laccum):
    """Get the valid time of a GRIB message."""
    return _valid_time_helper(grib_msg) if laccum else grib_msg.validDate


def _valid_time_helper(grib_msg):
    """
    Pygrib does not set the valid time correctly in case of total
    precipitation. Therefore, this helper function is necessary

    Parameters
    ----------
    grib_msg: Grib message object
        GRIB message of the file to read

    Returns
    -------
    validTime: datetime.datetime
    """
    validTime = datetime.datetime(
        grib_msg["yearOfEndOfOverallTimeInterval"],
        grib_msg["monthOfEndOfOverallTimeInterval"],
        grib_msg["dayOfEndOfOverallTimeInterval"],
        grib_msg["hourOfEndOfOverallTimeInterval"],
        grib_msg["minuteOfEndOfOverallTimeInterval"],
        grib_msg["secondOfEndOfOverallTimeInterval"],
    )
    return validTime


def _read_grid_file(grid_file_path):
    """
    Reads the coordinates of the unstructured triangular grid
    from the grid file

    Parameters
    ----------
    grid_file_path: str
        Path to the forecast data associated grid file

    Returns
    -------
    lon, lat: np.ndarray
        Longitude and latitude (in degrees) of the triangle centers
    """
    # Open grid file
    with nc.Dataset(grid_file_path) as ds:
        # Get lon/lat coordinates of triagle centers of the grid
        clon = np.rad2deg(np.ma.getdata(ds.variables["clon"][:]))
        clat = np.rad2deg(np.ma.getdata(ds.variables["clat"][:]))

    return clon, clat
