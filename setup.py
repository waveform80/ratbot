# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2012-2014 Dave Jones <dave@waveform.org.uk>.
#
# This file is part of ratbot comics.
#
# ratbot comics is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# ratbot comics is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# ratbot comics. If not, see <http://www.gnu.org/licenses/>.

"""A web application for publishing comics."""

# Python 3 compatibility
from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import os
import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

if sys.version_info[0] == 2:
    if not sys.version_info >= (2, 7):
        raise ValueError('This package requires Python 2.7 or newer')
elif sys.version_info[0] == 3:
    if not sys.version_info >= (3, 2):
        raise ValueError('This package requires Python 3.2 or newer')
else:
    raise ValueError('Unrecognized major version of Python')

HERE = os.path.abspath(os.path.dirname(__file__))

# Workaround <http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html>
try:
    import multiprocessing
except ImportError:
    pass

__project__      = 'ratbot'
__version__      = '2.0'
__author__       = 'Dave Jones'
__author_email__ = 'dave@waveform.org.uk'
__url__          = 'https://github.com/waveform80/ratbot'
__platforms__    = ['ALL']

__classifiers__ = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Web Environment',
    'Intended Audience :: End Users/Desktop',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: POSIX :: Linux',
    'Framework :: Pyramid',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Topic :: Multimedia :: Graphics :: Viewers',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ]

__keywords__ = [
    'comics',
    ]

__requires__ = [
    'pyramid<1.5dev',
    'sqlalchemy<1.0dev',
    'transaction',
    'pyramid_tm',
    'pyramid_beaker',
    'pyramid_debugtoolbar',
    'pyramid_mailer',
    'pyramid_exclog',
    'webhelpers<2.0dev',
    'zope.sqlalchemy',
    'waitress',
    'pillow<2.0dev',
    'pypdf2',
    'pytz',
    'bleach<2.0dev',
    'markdown<3.0dev',
    'docutils<1.0dev',
    'velruse<2.0dev',
    'formencode<2.0dev',
    ]

__extra_requires__ = {
    }

__entry_points__ = {
        'paste.app_factory': [
            'main = ratbot:main',
            ],
        'console_scripts': [
            'initialize_ratbot_db = ratbot.scripts.initializedb:main',
            ],
    }

# Add a py.test based "test" command
class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--verbose',
            '--cov', __project__,
            '--cov-report', 'term-missing',
            '--cov-report', 'html',
            '--cov-config', 'coverage.cfg',
            'tests',
            ]
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


def main():
    import io
    with io.open(os.path.join(HERE, 'README.rst'), 'r') as readme:
        setup(
            name                 = __project__,
            version              = __version__,
            description          = __doc__,
            long_description     = readme.read(),
            classifiers          = __classifiers__,
            author               = __author__,
            author_email         = __author_email__,
            url                  = __url__,
            license              = [
                c.rsplit('::', 1)[1].strip()
                for c in __classifiers__
                if c.startswith('License ::')
                ][0],
            keywords             = ' '.join(__keywords__),
            packages             = find_packages(),
            package_data         = {},
            include_package_data = True,
            platforms            = __platforms__,
            install_requires     = __requires__,
            extras_require       = __extra_requires__,
            zip_safe             = False,
            entry_points         = __entry_points__,
            tests_require        = ['pytest-cov', 'pytest', 'mock'],
            cmdclass             = {'test': PyTest},
            )


if __name__ == '__main__':
    main()
