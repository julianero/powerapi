# Copyright (C) 2018  University of Lille
# Copyright (C) 2018  INRIA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Module class PusherActor
"""

from smartwatts.actor import Actor
from smartwatts.handler import AbstractHandler
from smartwatts.report import PowerReport
from smartwatts.message import UnknowMessageTypeException, PoisonPillMessage
from smartwatts.handler import AbstractHandler, PoisonPillMessageHandler

class _PowerHandler(AbstractHandler):
    """
    HWPCHandler class
    """

    def __init__(self, database):
        self.database = database
        self.database.load()

    def handle(self, msg, state):
        """
        Override

        Save the msg in the database
        """
        if not isinstance(msg, PowerReport):
            raise UnknowMessageTypeException

        self.database.save(msg.serialize())
        return state


class PusherActor(Actor):
    """ PusherActor class """

    def __init__(self, name, report_type, database, verbose=False):
        Actor.__init__(self, name, verbose)
        self.report_type = report_type
        self.database = database

    def setup(self):
        """
        Override

        Specify for each kind of report the associate handler
        """
        self.handlers.append((self.report_type, _PowerHandler(self.database)))
        self.handlers.append((PoisonPillMessage, PoisonPillMessageHandler()))
