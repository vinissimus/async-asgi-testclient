#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open("README.md", "r") as f:
    readme = f.read()

with open("requirements.txt", "r") as f:
    requirements = f.readlines()

with open("test-requirements.txt", "r") as f:
    test_requirements = f.readlines()

setup(
    author="Jordi Masip",
    author_email="jordi@masip.cat",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    description="Async client for testing ASGI web servers",
    install_requires=requirements,
    license="GNU license",
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    name="asgi-testclient",
    keywords="asgi testclient",
    packages=find_packages(include=["asgi_testclient"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/vinissimus/asgi-testclient",
    version="0.1",
    zip_safe=False,
)
