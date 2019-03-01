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

import logging
import re
from functools import reduce

from powerapi.actor import Actor, State, SocketInterface

class FormulaState(State):

    def __init__(self, behaviour, socket_interface, logger, formula_id):
        State.__init__(self, behaviour, socket_interface, logger)
        self.formula_id = formula_id


class FormulaActor(Actor):
    """
    Formula abstract class. A Formula is an Actor which use data
    for computing some new useful power estimation.

    A Formula is design to be handle by a Dispatcher, and to send
    result to a Pusher.
    """

    def __init__(self, name, actor_pusher,
                 level_logger=logging.WARNING, timeout=None):
        """
        :param str name:                            Actor name
        :param powerapi.PusherActor actor_pusher: Pusher actor whom send
                                                    results
        :param int level_logger:                    Define logger level
        :param bool timeout:                        Time in millisecond to wait
                                                    for a message before called
                                                    timeout_handler.
        """
        Actor.__init__(self, name, level_logger, timeout)

        #: (powerapi.PusherActor): Pusher actor whom send results.
        self.actor_pusher = actor_pusher

        formula_id = reduce(lambda acc, x: acc + (re.search(r'^\(? ?\'(.*)\'\)?', x).group(1),), name.split(','), ())

        #: (powerapi.State): Basic state of the Formula.
        self.state = FormulaState(Actor._initial_behaviour,
                                  SocketInterface(name, timeout),
                                  self.logger, formula_id)

    def setup(self):
        """
        Formula basic setup, Connect the formula to the pusher
        """
        self.actor_pusher.connect_data()

    def terminated_behaviour(self):
        """
        Allow to close actor_pusher socket
        """
        self.actor_pusher.state.socket_interface.close()
