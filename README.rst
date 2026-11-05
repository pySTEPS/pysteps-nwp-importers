pysteps-nwp-importers
=====================

Pysteps plugin to import a variety of NWP rainfall forecasts. This plugin was created with Cookiecutter and makes the NWP importers findable for the Pysteps importer functionality after installation.


License
=======
* BSD license


Documentation
=============

NWP rainfall forecast importer using pysteps utilities. This plugin currently provides importers for:

* KNMI HARMONIE NWP forecasts
* BoM NWP forecasts
* RMI NWP forecasts
* DWD NWP forecasts

The importers follow the xarray-based data model of pysteps v2 (see
``pysteps.io.importers``): each importer returns an ``xarray.Dataset`` instead
of the ``(precip, quality, metadata)`` tuple of pysteps v1. The metadata is
stored in the dataset: the projection and institution in its attributes, the
unit, accumulation time, threshold and zero value in the attributes of the
precipitation variable, and the grid and valid times in its coordinates.

Once the plugin is installed, the importers are available through the pysteps
interface::

    from pysteps import io

    importer = io.get_method("bom_nwp", "importer")
    nwp_dataset = importer(filename)
    precip_var = nwp_dataset.attrs["precip_var"]
    nwp_dataset[precip_var]  # dimensions (time, y, x)

The DWD ICON-D2-RUC importer returns the rainfall on the unstructured ICON grid,
with dimensions (ens_number, time, cell). Use ``unstructured2regular`` to
reproject it onto the grid of another pysteps dataset, such as a radar
composite::

    from pysteps_nwp_importers.importer_dwd_nwp import unstructured2regular

    importer = io.get_method("dwd_nwp", "importer")
    nwp_dataset = importer(filename, varname="PR_GSP", grid_file_path=grid_file)
    nwp_dataset = unstructured2regular(nwp_dataset, radar_dataset)
    # dimensions (ens_number, time, y, x), on the grid of radar_dataset

``pysteps.blending.steps.forecast`` expects the NWP dataset to have an
``ens_number`` dimension. For a deterministic NWP forecast, add it with
``nwp_dataset.expand_dims(ens_number=[1])``.


Installation
============

The plugin requires pysteps>=2.0. As long as pysteps 2.0 is not released, install
pysteps from its main branch first (see the pysteps documentation).

The latest development version of pysteps_nwp_importers can be installed using
pip by running in a terminal::

    pip install git+https://github.com/pySTEPS/pysteps-nwp-importers

Test the plugin
===============

This plugin comes with a tester, which can also be used to test whether the plugin is correctly hooked up to pysteps.

Install pytest and run the tests with::

	pip install pytest
	pytest -v --tb=line

Credits
=======

This package was created with Cookiecutter_ and the `cookiecutter-pysteps-plugin`_ project template. 
The `cookiecutter-pysteps-plugin`_ template was adapted from the cookiecutter-pypackage_
template.

.. _cookiecutter-pypackage: https://github.com/audreyfeldroy/cookiecutter-pypackage
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-pysteps-plugin`: https://github.com/pysteps/cookiecutter-pysteps-plugin