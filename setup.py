import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "mast.datapower.web",
    version = "2.0.0",
    author = "Clifford Bressette",
    author_email = "cliffordbressette@mcindi.com",
    description = ("A Web GUI for MAST"),
    license = "GPLv3",
    keywords = "DataPower mast gui web",
    url = "http://github.com/mcindi/mast.datapower.web",
    namespace_packages=["mast", "mast.datapower"],
    packages=['mast', 'mast.datapower', 'mast.datapower.web'],
    entry_points = {
        'mastd_plugin': [
            'mastd_web_plugin = mast.datapower.web:Plugin'
        ]
    },
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Utilities",
        "License :: OSI Approved :: GPLv3",
    ],
)
