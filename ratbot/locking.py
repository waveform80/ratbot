# -*- coding: utf-8 -*-
# vim: set et sw=4 sts=4:

# Copyright 2011 Mateusz Kobos <http://code.activestate.com/recipes/577803-reader-writer-lock-with-priority-for-writers/>.
# Copyright 2016-2017 Dave Jones <dave@waveform.org.uk>.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import errno
import time
import threading


class Switch():
    """
    An auxiliary "light switch"-like object. The first thread to acquire the
    switch also acquires the lock associated with the switch. The last thread
    to release the switch also releases the lock associated with the switch.
    The switch supports the context manager protocol (the "with" statement).

    If the first and last threads can differ, you must use a primitive
    :class:`threading.Lock` as the value of the lock parameter. If the first
    and last threads will always be the same, you may use a re-entrant
    :class:`threading.RLock`.

    This implementation is derived from [1]_, sec. 4.2.2.

    .. [1] A.B. Downey: "The little book of semaphores", Version 2.1.5, 2008
    """
    def __init__(self, lock):
        self._counter = 0
        self._lock = lock
        self._mutex = threading.Lock()

    def acquire(self):
        with self._mutex:
            self._counter += 1
            if self._counter == 1:
                self._lock.acquire()

    def release(self):
        with self._mutex:
            if not self._counter:
                raise RuntimeError('Attempt to release an unacquired Switch')
            self._counter -= 1
            if self._counter == 0:
                self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


class SELock():
    """
    Synchronization object used in a solution of so-called second
    readers-writers problem.

    In this problem, many readers can simultaneously access a share, and a
    writer has an exclusive access to this share. Additionally, the following
    constraints should be met:

    1. no reader should be kept waiting if the share is currently opened for
       reading unless a writer is also waiting for the share,

    2. no writer should be kept waiting for the share longer than absolutely
       necessary.

    The implementation is based on [1]_, secs. 4.2.2, 4.2.6, 4.2.7 with a
    modification: adding an additional lock (readers_queue), in accordance with
    [2]_. The implementation provides two objects, ``shared`` and ``exclusive``
    which each support the context manager protocol along with the usual
    acquire and release methods.

    .. [1] A.B. Downey: "The little book of semaphores", Version 2.1.5, 2008
    .. [2] P.J. Courtois, F. Heymans, D.L. Parnas:
       "Concurrent Control with 'Readers' and 'Writers'",
       Communications of the ACM, 1971 (via [3]_)
    .. [3] http://en.wikipedia.org/wiki/Readers-writers_problem
    """

    def __init__(self):
        no_readers = threading.Lock()
        no_writers = threading.Lock()
        read_switch = Switch(no_writers)
        write_switch = Switch(no_readers)
        self.shared = _SharedLock(no_readers, read_switch)
        self.exclusive = _ExclusiveLock(no_writers, write_switch)


class _SharedLock():
    def __init__(self, no_readers, read_switch):
        self._no_readers = no_readers
        self._read_switch = read_switch
        self._readers_queue = threading.Lock()

    def acquire(self):
        with self._readers_queue:
            with self._no_readers:
                self._read_switch.acquire()

    def release(self):
        self._read_switch.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


class _ExclusiveLock():
    def __init__(self, no_writers, write_switch):
        self._no_writers = no_writers
        self._write_switch = write_switch

    def acquire(self):
        self._write_switch.acquire()
        self._no_writers.acquire()

    def release(self):
        self._no_writers.release()
        self._write_switch.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


class DirLock():
    """Provides a cross-platform inter-process lock via dir creation"""

    def __init__(self, path):
        self._path = os.path.join(path, 'lock')

    def acquire(self, blocking=True):
        # Using mkdir() as it's atomic on both Unix and Windows
        while True:
            try:
                os.mkdir(self._path)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                elif blocking:
                    time.sleep(0.1)
                else:
                    return False
            else:
                return True

    def release(self):
        os.rmdir(self._path)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.release()

