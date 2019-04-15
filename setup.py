#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages


setup(
    author="Jordi Masip",
    author_email='jordi@masip.cat',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Small and partial Obejct mapper on top of sqlalchemy for async",
    # install_requires=requirements,
    license="GNU license",
    # long_description=readme + '\n\n' + history,
    # long_description_content_type="text/markdown",
    include_package_data=True,
    keywords='asgi_test_client',
    name='asgi_test_client',
    packages=find_packages(include=['asgi_test_client']),
    # setup_requires=setup_requirements,
    test_suite='tests',
    # tests_require=test_requirements,
    url='https://github.com/vinissimus/asgi-test-client',
    # version=version,
    zip_safe=False,
)
