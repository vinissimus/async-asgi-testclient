#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import find_packages
from setuptools import setup

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
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    description="Async client for testing ASGI web applications",
    install_requires=requirements,
    license="MIT license",
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    name="async-asgi-testclient",
    keywords="async asgi testclient",
    packages=find_packages(include=["async_asgi_testclient"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/vinissimus/async-asgi-testclient",
    version="1.4.6",
    zip_safe=False,
)
