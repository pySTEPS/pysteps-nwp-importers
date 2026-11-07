"""
pysteps_nwp_importers.importer_bom_nwp
======================================

Module to import the BoM NWP forecasts.

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

import xarray as xr

from pysteps_nwp_importers._utils import netcdf_to_pysteps_dataset


def import_bom_nwp(filename, **kwargs):
    """Import a NetCDF with NWP rainfall forecasts regridded to a BoM Rainfields3
    using xarray.

    Parameters
    ----------
    filename: str
        Name of the file to import.

    Other Parameters
    ----------------
    varname: str, optional
        Name of the precipitation variable in the file. Defaults to
        "accum_prcp". If the variable is named "accum_prcp", the rainfall is
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

    varname = kwargs.get("varname", "accum_prcp")
    with xr.open_dataset(filename) as ds:
        return netcdf_to_pysteps_dataset(
            ds,
            varname,
            kwargs.get("varname_time", "time"),
            projection=_get_projection(ds),
            institution="Commonwealth of Australia, Bureau of Meteorology",
            accumulated=varname == "accum_prcp",
        )


def _get_projection(ds):
    """Get the PROJ.4 definition of the Albers equal area grid of a BoM file."""
    if "proj" not in ds or ds.proj.grid_mapping_name != "albers_conical_equal_area":
        return None
    proj = ds.proj
    lat_1, lat_2 = proj.standard_parallel
    return (
        f"+proj=aea  +lon_0={proj.longitude_of_central_meridian:.3f}"
        f" +lat_0={proj.latitude_of_projection_origin:.3f}"
        f" +lat_1={lat_1:.3f} +lat_2={lat_2:.3f}"
    )
