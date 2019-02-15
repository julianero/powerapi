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
Module powerapi-cli
"""

import argparse
import pickle
import logging
import signal
import zmq
from powerapi.database import MongoDB
from powerapi.pusher import PusherActor
from powerapi.formula import RAPLFormulaActor
from powerapi.dispatch_rule import HWPCDispatchRule, HWPCDepthLevel
from powerapi.filter import Filter
from powerapi.puller import PullerActor
from powerapi.report import HWPCReport, PowerReport
from powerapi.report_model import HWPCModel
from powerapi.dispatcher import DispatcherActor, RouteTable
from powerapi.message import OKMessage, StartMessage


class BadActorInitializationError(Exception):
    """ Error if actor doesn't answer with "OKMessage" """


def arg_parser_init():
    """ initialize argument parser"""
    parser = argparse.ArgumentParser(
        description="Start PowerAPI with the specified configuration.")

    # MongoDB input
    parser.add_argument("input_hostname", help="MongoDB input hostname")
    parser.add_argument("input_port", help="MongoDB input port", type=int)
    parser.add_argument("input_db", help="MongoDB input database")
    parser.add_argument("input_collection", help="MongoDB input collection")

    # MongoDB output
    parser.add_argument("output_hostname", help="MongoDB output hostname")
    parser.add_argument("output_port", help="MongoDB output port", type=int)
    parser.add_argument("output_db", help="MongoDB output database")
    parser.add_argument("output_collection", help="MongoDB output collection")

    # DispatchRule
    parser.add_argument("hwpc_dispatch_rule", help="Define the dispatch_rule rule, "
                        "Can be CORE, SOCKET or ROOT",
                        choices=['CORE', 'SOCKET', 'ROOT'])

    # Verbosity
    parser.add_argument("-v", "--verbose", help="Enable verbosity",
                        action="store_true", default=False)
    return parser


def main():
    """ Main function """

    ##########################################################################
    # Actor initialization step

    args = arg_parser_init().parse_args()
    if args.verbose:
        args.verbose = logging.DEBUG
    else:
        args.verbose = logging.NOTSET

    # Pusher
    output_mongodb = MongoDB(args.output_hostname, args.output_port,
                             args.output_db, args.output_collection,
                             save_mode=True)
    pusher = PusherActor("pusher_mongodb", PowerReport, output_mongodb,
                         level_logger=args.verbose)

    # Formula
    formula_factory = (lambda name, verbose:
                       RAPLFormulaActor(name, pusher, level_logger=verbose))

    # Dispatcher
    route_table = RouteTable()
    route_table.dispatch_rule(HWPCReport, HWPCDispatchRule(getattr(HWPCDepthLevel,
                                                         args.hwpc_dispatch_rule),
                                                 primary=True))

    dispatcher = DispatcherActor('dispatcher', formula_factory, route_table,
                                 level_logger=args.verbose)

    # Puller
    input_mongodb = MongoDB(args.input_hostname, args.input_port,
                            args.input_db, args.input_collection,
                            report_model=HWPCModel())
    report_filter = Filter()
    report_filter.filter(lambda msg: True, dispatcher)
    puller = PullerActor("puller_mongodb", input_mongodb,
                         report_filter, 0, level_logger=args.verbose,
                         autokill=True)

    ##########################################################################
    # Actor start step

    # Setup signal handler
    def term_handler(_, __):
        puller.join()
        dispatcher.join()
        pusher.join()
        exit(0)

    signal.signal(signal.SIGTERM, term_handler)
    signal.signal(signal.SIGINT, term_handler)

    # start actors
    context = zmq.Context()

    pusher.connect_control(context)
    pusher.start()
    dispatcher.connect_control(context)
    dispatcher.connect_data(context)
    dispatcher.start()
    puller.connect_control(context)
    puller.start()

    # Send StartMessage
    pusher.send_control(StartMessage())
    dispatcher.send_control(StartMessage())
    puller.send_control(StartMessage())

    # Wait for OKMessage
    poller = zmq.Poller()
    poller.register(pusher.state.socket_interface.control_socket, zmq.POLLIN)
    poller.register(dispatcher.state.socket_interface.control_socket,
                    zmq.POLLIN)
    poller.register(puller.state.socket_interface.control_socket, zmq.POLLIN)

    cpt_ok = 0
    while cpt_ok < 3:
        events = poller.poll(1000)
        msgs = [pickle.loads(sock.recv()) for sock, event in events
                if event == zmq.POLLIN]
        for msg in msgs:
            if isinstance(msg, OKMessage):
                cpt_ok += 1
            else:
                print(msg.error_message)
                puller.kill()
                puller.join()
                dispatcher.kill()
                dispatcher.join()
                pusher.kill()
                pusher.join()
                exit(0)

    ##########################################################################
    # Actor run step

    # wait
    puller.join()
    dispatcher.join()
    pusher.join()

    ##########################################################################


if __name__ == "__main__":
    main()