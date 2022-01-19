pysteps-nwp-importers
=====================

Pysteps plugin to import a variety of NWP rainfall forecasts. This plugin was created with Cookiecutter and makes the NWP importers findable for the Pysteps importer functionality after installation.



License
=======
* BSD license


Documentation
=============

NWP rainfall forecast importer using pysteps utilities. This plugin currently provides importers for:
- KNMI HARMONIE NWP forecasts
- BoM NWP forecasts
- RMI NWP forecasts


Installation instructions
=========================

Download the plugin here. Then, you can install the plugin, after pysteps has been installed, with:
	cd pysteps_nwp_importers
	pip install .

Test the plugin
===============

This plugin comes with a tester, which can also be used to test whether the plugin is correctly hooked up to pysteps.

Install pytest:

`pip install pytest`

`python setup.py build_ext -i`

To test it, run:

`pytest -v --tb=line`

Credits
=======

- This package was created with Cookiecutter_ and the `pysteps/cookiecutter-pysteps-plugin`_ project template.

.. Since this plugin template is based in the cookiecutter-pypackage template,
it is encouraged to leave the following credits to acknowledge Audrey Greenfeld's work.

- The `pysteps/cookiecutter-pysteps-plugin`_ template was adapted from the cookiecutter-pypackage_
template.

.. _cookiecutter-pypackage: https://github.com/audreyfeldroy/cookiecutter-pypackage

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`pysteps/cookiecutter-pysteps-plugin`: https://github.com/pysteps/cookiecutter-pysteps-plugin
