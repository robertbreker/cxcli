#!/usr/bin/env python3

import os
import setuptools

def get_version():
    here = os.path.abspath(os.path.dirname(__file__))
    with open("cxcli/__init__.py", "r") as fp:
        file_content = fp.readlines()
        for line in file_content:
            if line.startswith("__version__"):
                delim = '"' if '"' in line else "'"
                return line.split('"')[1]


with open("requirements.txt") as f:
    required = f.read().splitlines()

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cxcli",
    version=get_version(),
    author="Robert Breker",
    author_email="",
    description="Experimental CLI for Citrix Cloud",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/robertbreker/cxcli",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "cx=cxcli.clidriver:main",
        ],
    },
    python_requires=">=3.6",
    install_requires=required,
)
