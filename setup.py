# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

# Add the plugin dependencies here
requirements = ["numpy", "xarray", "dask", "netCDF4"]

# Add the packages needed to build the package.
setup_requirements = ['pytest-runner']

test_requirements = ['pytest>=3']

setup(
    author="Ruben Imhoff",
    author_email='ruben.imhoff@deltares.nl',
    python_requires='>=3.7',
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Pysteps plugin to import a variety of NWP rainfall forecasts",
    install_requires=requirements,
    license="BSD license",
    long_description=readme,
    test_suite='tests',
    tests_require=test_requirements,
    include_package_data=True,
    keywords=['pysteps_nwp_importers', 'pysteps' , 'plugin', 'importer'],
    name='pysteps_nwp_importers',
    packages=find_packages(),
    setup_requires=setup_requirements,
    # Entry points
    # ~~~~~~~~~~~~
    #
    # This is the most important part of the plugin setup script.
    # Entry points are a mechanism for an installed python distribution to advertise
    # some of the components installed (packages, modules, and scripts) to other
    # applications (in our case, pysteps).
    # https://packaging.python.org/specifications/entry-points/
    #
    # An entry point is defined by three properties:
    # - The group that an entry point belongs indicate the kind of functionality that
    #   provides. For the pysteps importers use the "pysteps.plugins.importers" group.
    # - The unique name that is used to identify this entry point in the
    #   "pysteps.plugins.importers" group.
    # - A reference to a Python object. For the pysteps importers, the object should
    #   point to a importer function, and should have the following form:
    #   package_name.module:function.
    # The setup script uses a dictionary mapping the entry point group names to a list
    # of strings defining the importers provided by this package (our plugin).
    # The general form of the entry points dictionary is:
    # entry_points={
    #     "group_name": [
    #         "entry_point_name=package_name.module:function",
    #         "entry_point_name=package_name.module:function2",
    #     ]
    # },
    entry_points={
        'pysteps.plugins.importers': [
            'import_knmi_nwp=pysteps_nwp_importers.importer_knmi_nwp:import_knmi_nwp',
            'import_bom_nwp=pysteps_nwp_importers.importer_bom_nwp:import_bom_nwp',
            'import_rmi_nwp=pysteps_nwp_importers.importer_rmi_nwp:import_rmi_nwp',
        ]
    },
    version='1.6',
    zip_safe=False,
)
