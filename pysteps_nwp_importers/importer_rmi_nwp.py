"""
pysteps_nwp_importers.importer_rmi_nwp
======================================

Module to import the RMI NWP forecasts.

The importer returns an xarray dataset that follows the pysteps data model
described in :py:mod:`pysteps.io.importers`. The forecast rainfall fields are
stored in the data variable named by ``dataset.attrs["precip_var"]``, with
dimensions (time, y, x). The metadata is stored as follows:

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
| precip_var ``units``         | the physical unit of the data: 'mm'          |
+------------------------------+----------------------------------------------+
| precip_var ``accutime``      | the accumulation time in minutes of the data |
+------------------------------+----------------------------------------------+
| precip_var ``threshold``     | the rain/no rain threshold with the same     |
|                              | unit and accutime of the data                |
+------------------------------+----------------------------------------------+
| precip_var ``zerovalue``     | the value assigned to the no rain pixels with|
|                              | the same unit and accutime of the data       |
+------------------------------+----------------------------------------------+
| x, y coordinates             | cell centres in ``units``, regularly spaced  |
|                              | by ``stepsize``                              |
+------------------------------+----------------------------------------------+
| time coordinate              | valid times, regularly spaced by ``stepsize``|
|                              | (in seconds)                                 |
+------------------------------+----------------------------------------------+

"""

import numpy as np
import xarray as xr

from pysteps_nwp_importers._utils import (
    disaggregate_accumulation,
    get_threshold_value,
    get_timestep_seconds,
    normalize_unit,
    to_pysteps_dataset,
)
from pysteps_nwp_importers.exceptions import MissingOptionalDependency

try:
    import netCDF4

    NETCDF4_IMPORTED = True
except ImportError:
    NETCDF4_IMPORTED = False

try:
    import dask

    DASK_IMPORTED = True
except ImportError:
    DASK_IMPORTED = False


def import_rmi_nwp(filename, **kwargs):
    """Import a NetCDF with NWP rainfall forecasts from RMI using xarray.

    Parameters
    ----------
    filename: str
        Name of the file to import.

    Other Parameters
    ----------------
    varname: str, optional
        Name of the precipitation variable in the file. Defaults to
        "precipitation". If the variable is named "accum_prcp", the rainfall is
        assumed to be accumulated since the start of the forecast and it is
        disaggregated into accumulations per time step. The first time step is
        dropped in that case.
    varname_time: str, optional
        Name of the time coordinate in the file. Defaults to "time".

    Returns
    -------
    dataset: xarray.Dataset
        Dataset containing the forecast rainfall fields, with dimensions
        (time, y, x), and the associated metadata, following the pysteps data
        model described in :py:mod:`pysteps.io.importers`.
    """

    if not NETCDF4_IMPORTED:
        raise MissingOptionalDependency(
            "netCDF4 package is required to import RMI NWP rainfall "
            "products but it is not installed"
        )

    if not DASK_IMPORTED:
        raise MissingOptionalDependency(
            "dask package is required to import RMI NWP regridded rainfall "
            "products but it is not installed"
        )

    varname = kwargs.get("varname", "precipitation")
    varname_time = kwargs.get("varname_time", "time")

    with _import_rmi_nwp_data_xr(filename, **kwargs) as ds:
        metadata = _import_rmi_nwp_geodata_xr(ds, **kwargs)
        precip = ds[varname].transpose(varname_time, "y", "x").values
        times = ds[varname_time].values
        x = ds.x.values
        y = ds.y.values

    # if data variable is named accum_prcp
    # it is assumed that NWP rainfall data is accumulated
    # so it needs to be disagregated by time step
    if varname == "accum_prcp":
        print("Rainfall values are accumulated. Disaggregating by time step")
        precip, times = disaggregate_accumulation(precip, times)

    return to_pysteps_dataset(precip, x, y, times, metadata)


def _import_rmi_nwp_data_xr(filename, **kwargs):
    return xr.open_dataset(filename)


def _import_rmi_nwp_geodata_xr(
    ds_in,
    **kwargs,
):
    varname = kwargs.get("varname", "precipitation")
    varname_time = kwargs.get("varname_time", "time")
    projdef = None
    if "proj4string" in ds_in.attrs:
        projdef = ds_in.proj4string

    # get the accumulation period (in minutes)
    time_step = get_timestep_seconds(ds_in[varname_time].values) // 60

    # get the units of precipitation
    units = None
    if "units" in ds_in[varname].attrs:
        units = normalize_unit(ds_in[varname].units)

    # move to meters if coordinates in kilometers
    if "units" in ds_in.x.attrs:
        if ds_in.x.units == "km":
            ds_in["x"] = ds_in.x * 1000.0
            ds_in.x.attrs.update({"units": "m"})
            ds_in["y"] = ds_in.y * 1000.0
            ds_in.y.attrs.update({"units": "m"})

    # Rainfall field of the first time step, used for the threshold and zerovalue
    da_rainfall = ds_in[varname].isel({varname_time: 0})

    # Fill the metadata dictionary
    metadata = dict(
        cartesian_unit=ds_in.x.units,
        unit=units,
        zerovalue=np.nanmin(da_rainfall),
        institution="Royal Meteorological Institute of Belgium",
        projection=projdef,
        threshold=get_threshold_value(da_rainfall.values),
        accutime=time_step,
    )

    return metadata
