#!/usr/bin/env python3

import setuptools

with open("requirements.txt") as f:
    required = f.read().splitlines()

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cxcli",
    version="0.1.1",
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
