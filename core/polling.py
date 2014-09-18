# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Thomas Amland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import xbmc
from watchdog.observers.api import EventEmitter
from watchdog.events import DirDeletedEvent, DirCreatedEvent, FileCreatedEvent, FileDeletedEvent
import settings


def _paused():
    return xbmc.Player().isPlaying() and settings.PAUSE_ON_PLAYBACK


def hidden(path):
    return path.startswith(b'.') or path.startswith(b'_UNPACK')


class MtimeSnapshot(object):
    def __init__(self, root, get_mtime):
        self._root = root
        self._mtime = get_mtime(root)

    def diff(self, other):
        modified = [self._root] if self._mtime != other._mtime else []
        return [], [], modified


class FileSnapshot(object):
    def __init__(self, root, walker):
        self._files = set()
        for dirs, files in walker(root):
            self._files.update(files)

    def diff(self, other):
        created = other._files - self._files
        deleted = self._files - other._files
        return created, deleted, []


class _PollerType(type):
    def __str__(self):
        return "%s(recursive=%s, interval=%d)" % (
            self.__name__, self.recursive, self.polling_interval)


class PollerBase(EventEmitter):
    __metaclass__ = _PollerType
    polling_interval = -1
    recursive = True

    def __init__(self, event_queue, watch, timeout=1):
        EventEmitter.__init__(self, event_queue, watch, timeout)
        self._snapshot = None

    def _take_snapshot(self):
        """Take and return a snapshot of this emitters root path."""
        pass

    def is_offline(self):
        """Whether the file system this emitter is watching is offline."""
        return False

    def queue_events(self, timeout):
        if self.stopped_event.wait(self.polling_interval):
            return
        if _paused():
            return
        if self.is_offline():
            return
        if self._snapshot is None:
            self._snapshot = self._take_snapshot()
            return

        new_snapshot = self._take_snapshot()
        files_created, files_deleted, dirs_modified = self._snapshot.diff(new_snapshot)
        self._snapshot = new_snapshot

        for path in files_created:
            self.queue_event(FileCreatedEvent(path))
        for path in files_deleted:
            self.queue_event(FileDeletedEvent(path))

        # TODO: fix event handler and remove this
        if dirs_modified:
            self.queue_event(DirDeletedEvent(self.watch.path + '*'))
        if dirs_modified:
            self.queue_event(DirCreatedEvent(self.watch.path + '*'))
