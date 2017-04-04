# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2012-2016 Dave Jones <dave@waveform.org.uk>.
#
# This file is part of ratbot comics.
#
# ratbot comics is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# ratbot comics is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# ratbot comics. If not, see <http://www.gnu.org/licenses/>.

"""
Provides a refreshable license repository.

License information is sourced from opendefinition.org in JSON format. A
routine is provided for construction a license factory from Paste style
settings, and the resulting object can be refreshed from opendefinition.org at
any time.  The license data is cached and only re-read weekly.
"""

import os
import io
import json
import time
import errno
from datetime import datetime, timedelta
from contextlib import closing
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from .locking import DirLock


__all__ = [
    'licenses_factory_from_settings',
    'License',
    'LicensesFactory',
    'DummyLicensesFactory',
    ]


# See <http://licenses.opendefinition.org> for the Licenses API. The URL below
# links to a JSON database of all licenses with various attributes
LICENSES_API_ALL = 'http://licenses.opendefinition.org/licenses/groups/all.json'


class License():
    def __init__(self, **attr):
        self.domains = set()
        if attr.get('domain_content', False):
            self.domains |= {'content'}
        if attr.get('domain_data', False):
            self.domains |= {'data'}
        if attr.get('domain_software', False):
            self.domains |= {'software'}
        self.family = attr.get('family', '')
        self.id = attr['id']
        self.is_generic = bool(attr.get('is_generic', ''))
        self.is_od_compliant = attr.get('is_od_compliant', '') == 'approved'
        self.is_osd_compliant = attr.get('is_osd_compliant', '') == 'approved'
        self.maintainer = attr.get('maintainer', '')
        self.active = attr['status'] == 'active'
        self.title = attr['title']
        self.url = attr.get('url', '')

    @property
    def is_open(self):
        return self.is_od_compliant or self.is_osd_compliant


class DummyLicensesFactory():
    def __call__(self):
        return {'notspecified': License(
            id='notspecified',
            is_generic=True,
            status='active',
            title='License Not Specified')}


class LicensesFactory():
    """Factory class which returns a dictionary of licenses when called"""

    def __init__(self, cache_dir):
        try:
            os.makedirs(cache_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        self._cache_file = os.path.join(cache_dir, 'all.json')
        self._cache_lock = DirLock(cache_dir)

    def update_mandatory(self):
        """Guarantees to update the cache"""
        with self._cache_lock:
            self._update_cache()

    def update_optional(self, timeout=1):
        """Attempts to update the cache, failing silently on lock timeout"""
        if self._cache_lock.acquire(blocking=False):
            try:
                self._update_cache()
            finally:
                self._cache_lock.release()

    def _update_cache(self):
        """Attempts to update the cache - should not be called directly"""
        # Download the new defs to a temoprary file
        with io.open(self._cache_file + '.new', 'wb') as target:
            with closing(urlopen(LICENSES_API_ALL, timeout=10)) as source:
                while True:
                    data = source.read(1024**2)
                    if not data:
                        break
                    target.write(data)

        # XXX Should validate the new cache file here
        # Renames within the same file-system are atomic, i.e. everything that
        # attempts to read the cache before this gets the old file and
        # everything afterwards gets the new cache - no process gets a
        # partially written cache file
        os.rename(self._cache_file + '.new', self._cache_file)

    def __call__(self):
        """Return a dictionary of License instances keyed by id"""
        if not os.path.exists(self._cache_file):
            # If the cache file doesn't exist we must create it in order to
            # return any results
            self.update_mandatory()
        elif (datetime.utcfromtimestamp(os.stat(self._cache_file).st_mtime) <
                (datetime.now() - timedelta(days=7))):
            # If the cache file is merely stale we'll attempt to get a lock and
            # update it, but if we can't get a lock just use the stale file
            self.update_optional()
        return {
            key: License(**value)
            for (key, value) in json.load(io.open(self._cache_file, 'rb')).items()
            }


def licenses_factory_from_settings(settings):
    return LicensesFactory(settings['licenses.cache_dir'])

