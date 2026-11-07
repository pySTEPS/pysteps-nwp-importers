"""
pysteps_nwp_importers.importer_knmi_nwp
=======================================

Module to import the KNMI HARMONIE NWP forecasts.

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


def import_knmi_nwp(filename, **kwargs):
    """Import a NetCDF with HARMONIE NWP rainfall forecasts from KNMI using
    xarray.

    Parameters
    ----------
    filename: str
        Name of the file to import.

    Other Parameters
    ----------------
    varname: str, optional
        Name of the precipitation variable in the file. Defaults to "P_fc".
    varname_time: str, optional
        Name of the time coordinate in the file. Defaults to "time".

    Returns
    -------
    dataset: xarray.Dataset
        Dataset containing the forecast rainfall fields, with dimensions
        (time, y, x), and the associated metadata, following the pysteps data
        model described in :py:mod:`pysteps.io.importers`.
    """

    with xr.open_dataset(filename) as ds:
        return netcdf_to_pysteps_dataset(
            ds,
            kwargs.get("varname", "P_fc"),
            kwargs.get("varname_time", "time"),
            projection=ds.crs.proj4_params,
            institution=ds.attrs["institution"],
            clip_negative=True,
        )
