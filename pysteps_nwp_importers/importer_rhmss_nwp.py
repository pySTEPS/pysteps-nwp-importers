"""
pysteps_nwp_importers.importer_rhmss_nwp
========================================

Module to import NWP precipitation forecasts distributed by the Republic
Hydrometeorological Service of Serbia (RHMSS) as GRIB edition 1 files on a
regular latitude/longitude grid.

It was written for the two products that RHMSS provides:

* the WRF-NMM forecasts (``NMM<YYYYMMDD>``): a single deterministic run with
  3-hourly *period* accumulations of total precipitation (``tp``) in
  ``kg m**-2`` on a 0.05 degree grid;
* the ECMWF IFS control and ensemble runs (``ifs_<YYYYMMDD>control`` /
  ``ifs_<YYYYMMDD>ens``): hourly total precipitation *accumulated since the
  forecast initialization* and expressed in metres, on a 0.1 degree grid,
  optionally with 50 perturbed members.

Both flavours are handled by the same importer: the accumulation convention is
detected from the GRIB time range indicator, and the fields are always returned
as precipitation *depth per time step* in mm, together with the length of that
time step in ``metadata["accutime"]``.

The metadata dictionary contains the following key-value pairs:

.. tabularcolumns:: |p{2cm}|L|

+------------------+----------------------------------------------------------+
|       Key        |                Value                                     |
+==================+==========================================================+
|   projection     | PROJ.4-compatible projection definition                  |
+------------------+----------------------------------------------------------+
|   x1             | x-coordinate of the lower-left corner of the data raster |
+------------------+----------------------------------------------------------+
|   y1             | y-coordinate of the lower-left corner of the data raster |
+------------------+----------------------------------------------------------+
|   x2             | x-coordinate of the upper-right corner of the data raster|
+------------------+----------------------------------------------------------+
|   y2             | y-coordinate of the upper-right corner of the data raster|
+------------------+----------------------------------------------------------+
|   xpixelsize     | grid resolution in x-direction                           |
+------------------+----------------------------------------------------------+
|   ypixelsize     | grid resolution in y-direction                           |
+------------------+----------------------------------------------------------+
|   cartesian_unit | the physical unit of the x- and y-coordinates: 'degrees' |
+------------------+----------------------------------------------------------+
|   yorigin        | a string specifying the location of the first element in |
|                  | the data raster w.r.t. y-axis:                           |
|                  | 'upper' = upper border, 'lower' = lower border           |
+------------------+----------------------------------------------------------+
|   institution    | name of the institution who provides the data            |
+------------------+----------------------------------------------------------+
|   unit           | the physical unit of the data: 'mm'                      |
+------------------+----------------------------------------------------------+
|   transform      | the transformation of the data: None                     |
+------------------+----------------------------------------------------------+
|   accutime       | the accumulation time in minutes of the data, float      |
+------------------+----------------------------------------------------------+
|   threshold      | the rain/no rain threshold with the same unit,           |
|                  | transformation and accutime of the data                  |
+------------------+----------------------------------------------------------+
|   zerovalue      | the value assigned to the no rain pixels with the same   |
|                  | unit, transformation and accutime of the data            |
+------------------+----------------------------------------------------------+
|   timestamps     | the valid time of every returned time step               |
+------------------+----------------------------------------------------------+
|   leadtimes      | the lead time in minutes of every returned time step     |
+------------------+----------------------------------------------------------+
|   ensemble_members | the GRIB perturbation numbers, only for ensemble input |
+------------------+----------------------------------------------------------+
"""

import datetime

import numpy as np

try:
    import pygrib

    PYGRIB_IMPORTED = True
except ImportError:
    PYGRIB_IMPORTED = False

from pysteps_nwp_importers.exceptions import MissingOptionalDependency

# GRIB1 code table 4: unit of time range -> length in minutes
_TIME_UNIT_TO_MINUTES = {
    0: 1.0,  # minute
    1: 60.0,  # hour
    2: 1440.0,  # day
    10: 180.0,  # 3 hours
    11: 360.0,  # 6 hours
    12: 720.0,  # 12 hours
    13: 15.0,  # 15 minutes
    14: 30.0,  # 30 minutes
    254: 1.0 / 60.0,  # second
}

# conversion of the GRIB unit of the precipitation variable to mm
_UNIT_TO_MM = {"kg m**-2": 1.0, "kg m-2": 1.0, "mm": 1.0, "m": 1000.0}


def import_rhmss_nwp(filename, **kwargs):
    """
    Import a GRIB1 file with RHMSS NWP precipitation forecasts using pygrib.

    Parameters
    ----------
    filename: str
        Name of the file to import.

    Other Parameters
    ----------------
    varname: str
        GRIB short name of the variable to read. Defaults to "tp"
        (total precipitation).
    member: int or None
        Perturbation number of the ensemble member to read. By default all
        members present in the file are read, which adds a leading ensemble
        dimension to the returned array. Ignored for deterministic files.
    accumulation: {"auto", "period", "since_init"}
        How the accumulated variable in the file has to be interpreted.
        "period" means that every message holds the accumulation over the
        interval between two consecutive forecast steps (WRF-NMM), while
        "since_init" means that every message holds the accumulation since the
        forecast initialization and has to be differenced (IFS). The default
        "auto" derives this from the GRIB start and end step.
    keep_analysis: bool
        Whether to keep the (all-zero) field valid at the analysis time.
        Defaults to False, so that the first returned field is the first
        accumulation interval of the forecast.

    Returns
    -------
    tuple
        A tuple containing the following:

        - precipitation : np.ndarray, float64
            Precipitation depth in mm per time step, with dimensions
            [time, rows, cols], or [members, time, rows, cols] if the file
            contains more than one ensemble member and no ``member`` was
            selected.
        - quality : None
            There is no quality information in the GRIB files.
        - metadata : dict
            Associated metadata (pixel sizes, map projection, etc.; see the
            documentation of pysteps_nwp_importers.importer_rhmss_nwp).
    """
    if not PYGRIB_IMPORTED:
        raise MissingOptionalDependency(
            "pygrib package is required to import RHMSS NWP precipitation "
            "forecasts but it is not installed"
        )

    varname = kwargs.get("varname", "tp")
    member = kwargs.get("member", None)
    accumulation = kwargs.get("accumulation", "auto")
    keep_analysis = kwargs.get("keep_analysis", False)

    try:
        grib_file = pygrib.open(filename)
    except Exception as err:
        raise IOError(f"File {filename} could not be opened, because of: {err}")

    try:
        grib_msgs = [msg for msg in grib_file.read() if msg["shortName"] == varname]
    finally:
        grib_file.close()

    if not grib_msgs:
        raise IOError(f"File {filename} does not contain the variable '{varname}'")

    reference_times = {_analysis_time(msg) for msg in grib_msgs}
    if len(reference_times) > 1:
        raise IOError("File should contain only one forecast initialization")
    reference_time = reference_times.pop()

    # The lead time of a message is the *end* of its accumulation interval.
    # pygrib's validDate is derived from startStep and is therefore wrong for
    # the interval-accumulated WRF-NMM messages, so it is not used here.
    lead_times = np.array([_lead_time(msg) for msg in grib_msgs])
    members = np.array([_member_number(msg) for msg in grib_msgs])

    if accumulation == "auto":
        accumulation = _detect_accumulation(grib_msgs)
    if accumulation not in ("period", "since_init"):
        raise ValueError(
            f"Unknown accumulation '{accumulation}', "
            "expected 'auto', 'period' or 'since_init'"
        )

    unique_members = np.unique(members)
    if member is not None:
        if member not in unique_members:
            raise ValueError(
                f"Member {member} not in the file, available members are "
                f"{unique_members.tolist()}"
            )
        unique_members = np.array([member])
    unique_lead_times = np.unique(lead_times)

    # Read the geodata and the unit from the first message
    metadata, grid_shape, flip_rows = _import_rhmss_nwp_geodata(grib_msgs[0])
    unit = grib_msgs[0]["units"]
    if unit not in _UNIT_TO_MM:
        raise IOError(f"Cannot convert the unit '{unit}' of '{varname}' to mm")
    to_mm = _UNIT_TO_MM[unit]

    # Fill the (members, time, y, x) array
    precip = np.full(
        (len(unique_members), len(unique_lead_times)) + grid_shape, np.nan
    )
    for msg, lead_time, msg_member in zip(grib_msgs, lead_times, members):
        if msg_member not in unique_members:
            continue
        i = int(np.searchsorted(unique_members, msg_member))
        j = int(np.searchsorted(unique_lead_times, lead_time))
        values = np.asarray(msg["values"], dtype=float)
        values[values >= msg["missingValue"]] = np.nan
        precip[i, j] = values[::-1] if flip_rows else values

    precip *= to_mm

    if accumulation == "since_init":
        # Difference the accumulations since initialization. The resulting
        # field at index j is the accumulation between step j-1 and step j.
        precip = np.diff(precip, axis=1, prepend=precip[:, :1] * 0.0)
        accutimes = np.diff(unique_lead_times, prepend=0.0)
    else:
        # The length of the interval is encoded in the message itself.
        intervals = {
            lead_time: _accumulation_length(msg)
            for msg, lead_time in zip(grib_msgs, lead_times)
        }
        accutimes = np.array([intervals[lt] for lt in unique_lead_times])

    if not keep_analysis:
        keep = unique_lead_times > 0
        precip = precip[:, keep]
        unique_lead_times = unique_lead_times[keep]
        accutimes = accutimes[keep]

    accutime = float(np.median(accutimes))
    if not np.allclose(accutimes, accutime):
        raise IOError(
            "The accumulation period is not constant over the forecast: "
            f"{accutimes.tolist()} minutes"
        )

    # Small negative values can appear after differencing an accumulation
    precip = np.where(precip < 0.0, 0.0, precip)

    if precip.shape[0] == 1:
        precip = precip[0]
    else:
        metadata["ensemble_members"] = unique_members

    metadata["unit"] = "mm"
    metadata["transform"] = None
    metadata["accutime"] = accutime
    metadata["zerovalue"] = 0.0
    metadata["threshold"] = _get_threshold_value(precip)
    metadata["leadtimes"] = unique_lead_times
    metadata["timestamps"] = np.array(
        [
            reference_time + datetime.timedelta(minutes=float(lead_time))
            for lead_time in unique_lead_times
        ]
    )
    # kept for consistency with the other importers of this plugin
    metadata["time_stamps"] = metadata["timestamps"]

    return precip, None, metadata


def _import_rhmss_nwp_geodata(grib_msg):
    """
    Extract the grid definition of a GRIB message on a regular lat/lon grid.

    Returns the pysteps geodata dictionary, the (rows, cols) shape of the grid
    and a flag telling whether the rows of the message have to be reversed to
    obtain a north-up (yorigin="upper") raster.
    """
    if grib_msg["gridType"] != "regular_ll":
        raise IOError(
            f"Expected a regular lat/lon grid, got '{grib_msg['gridType']}'. "
            "Interpolate the file to a regular grid first, e.g. with "
            "'cdo remapbil'."
        )

    _, lat, lon = grib_msg.data()
    n_rows, n_cols = lat.shape

    xpixelsize = abs(float(lon[0, 1] - lon[0, 0]))
    ypixelsize = abs(float(lat[1, 0] - lat[0, 0]))

    # pysteps expects x1/y1 and x2/y2 to be the outer edges of the raster,
    # whereas the GRIB coordinates are the centres of the corner grid cells.
    x1 = float(lon.min()) - xpixelsize / 2.0
    x2 = float(lon.max()) + xpixelsize / 2.0
    y1 = float(lat.min()) - ypixelsize / 2.0
    y2 = float(lat.max()) + ypixelsize / 2.0

    # Always return a north-up raster: this is the pysteps convention and the
    # one assumed by pysteps.utils.reproject_grids.
    flip_rows = bool(lat[0, 0] < lat[-1, 0])

    proj_params = grib_msg.projparams
    proj_def = " ".join(f"+{key}={value}" for key, value in proj_params.items())

    metadata = dict(
        projection=proj_def,
        cartesian_unit="degrees",
        x1=x1,
        x2=x2,
        y1=y1,
        y2=y2,
        xpixelsize=xpixelsize,
        ypixelsize=ypixelsize,
        yorigin="upper",
        institution=str(grib_msg["centre"]),
    )

    return metadata, (n_rows, n_cols), flip_rows


def _analysis_time(grib_msg):
    """Return the forecast initialization time of a GRIB message."""
    date = int(grib_msg["dataDate"])
    time = int(grib_msg["dataTime"])
    return datetime.datetime(
        date // 10000, (date // 100) % 100, date % 100, time // 100, time % 100
    )


def _step_unit_minutes(grib_msg):
    """Return the length in minutes of the step unit of a GRIB message."""
    for key in ("stepUnits", "indicatorOfUnitOfTimeRange", "unitOfTimeRange"):
        if grib_msg.has_key(key):
            unit = int(grib_msg[key])
            if unit in _TIME_UNIT_TO_MINUTES:
                return _TIME_UNIT_TO_MINUTES[unit]
    # hours is the GRIB default
    return 60.0


def _lead_time(grib_msg):
    """Return the lead time in minutes of the end of the validity interval."""
    return float(grib_msg["endStep"]) * _step_unit_minutes(grib_msg)


def _accumulation_length(grib_msg):
    """Return the length in minutes of the validity interval of a message."""
    length = float(grib_msg["endStep"]) - float(grib_msg["startStep"])
    return length * _step_unit_minutes(grib_msg)


def _member_number(grib_msg):
    """Return the ensemble perturbation number of a GRIB message, or 0."""
    if grib_msg.has_key("perturbationNumber"):
        return int(grib_msg["perturbationNumber"])
    return 0


def _detect_accumulation(grib_msgs):
    """
    Decide whether the messages hold period accumulations or accumulations
    since the forecast initialization.
    """
    intervals = np.array([_accumulation_length(msg) for msg in grib_msgs])
    starts = np.array([float(msg["startStep"]) for msg in grib_msgs])
    if np.any(intervals > 0.0) and np.any(starts > 0.0):
        # e.g. WRF-NMM: 0-3, 3-6, 6-9, ...
        return "period"
    # e.g. IFS: every message is valid from the initialization onwards
    return "since_init"


def _get_threshold_value(precip):
    """
    Get the rain/no rain threshold with the same unit, transformation and
    accutime of the data.

    If all the values are NaNs, the returned value is `np.nan`. Otherwise,
    np.min(precip[precip > precip.min()]) is returned.

    Parameters
    ----------
    precip: np.ndarray
        Array containing the precipitation fields from which the threshold
        value is to be extracted.

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
            return float(np.min(_precip[above_min_mask]))
        return float(min_precip)
    return np.nan
