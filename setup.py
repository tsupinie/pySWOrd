import os, sys
from setuptools import setup, find_packages

pkgname = "pySWOrd"

### GET VERSION INFORMATION ###
setup_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(setup_path, pkgname.lower()))
import _pysword_version as version
ver = version.get_version()
sys.path.pop()

### ACTUAL SETUP VALUES ###
name = pkgname
version = ver
author = "Tim Supinie"
author_email = "tsupinie@ou.edu"
description = "SWO Reader"
long_description = "Parses SPC severe weather outlooks and pulls out the outlook regions."
license = "GPLv3"
keywords = "meteorology spc outlook"
url = "https://github.com/tsupinie/pySWOrd"
packages = ['pysword']
package_data = {"": ["*.md", "*.txt", "data/outline.pkl"],}
include_package_data = True
classifiers = []

setup(
    name = name,
    version = version,
    author = author,
    author_email = author_email,
    description = description,
    long_description = long_description,
    license = license,
    keywords = keywords,
    url = url,
    packages = packages,
    package_data = package_data,
    include_package_data = include_package_data,
    classifiers = classifiers
)
