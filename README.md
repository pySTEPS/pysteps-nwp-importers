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

You can install the plugin with pip:

	pip install pysteps-nwp-importers

Test the plugin
===============

This plugin comes with a tester, which can also be used to test whether the plugin is correctly hooked up to pysteps.

Install pytest and run the tests with

	pip install pytest
	pytest -v --tb=line

Credits
=======

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [cookiecutter-pysteps-plugin](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template. 

Since this plugin template is based in the cookiecutter-pypackage template, it is encouraged to leave the following credits to acknowledge Audrey Greenfeld's work.

The [cookiecutter-pysteps-plugin](https://github.com/audreyfeldroy/cookiecutter-pypackage) template was adapted from the [cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) template.
