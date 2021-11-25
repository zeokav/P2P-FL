import gc
import sys
import threading
import time
import datetime
import logging

from ctypes import cdll
import ctypes
from helper import *

gc.disable()

default_logger = logging.getLogger('tunnel.logger')
default_logger.disabled = False
default_logger.setLevel(logging.CRITICAL)

FUNC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)

# Reusing the same opcodes
OP_RECV = 0x00
OP_CLIENT_WAKE_UP = 0x01
OP_CLIENT_READY = 0x02
OP_CLIENT_UPDATE = 0x03
OP_CLIENT_EVAL = 0x04
OP_INIT = 0x05
OP_REQUEST_UPDATE = 0x06
OP_STOP_AND_EVAL = 0x07
OP_CLIENT_EVICTED = 0x08
OP_SELF_UP = 0x09
OP_CLIENT_LIST_UPDATE = 0x0a

on_recv_cb = None
on_init_cb = None
on_wakeup_cb = None
on_client_evict_cb = None
on_self_up_cb = None
on_client_list_update_cb = None


class FLPeer:
    def __init__(self, host, port, bootstrap_address=None):
        self.all_ids = set()
        self.cid = None
        self.shut_down = False

        self.lib = cdll.LoadLibrary('./libp2p.so')
        self.lib.Init_p2p.restype = ctypes.c_char_p
        self.lib.Write.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_byte]
        self.bootstrap_address = bootstrap_address

        self.host = host
        self.port = port

        self.register_handles()

        self.stat_printer = threading.Thread(target=self.print_stats)
        self.stat_printer.start()

    def print_stats(self):
        while not self.shut_down:
            print("\n[{}]\n\tPeer list: {}".format(datetime.datetime.now(), self.all_ids))
            time.sleep(5)

    def register_handles(self):
        def on_recv(src):
            print("On receive")
            data = pickle_string_to_obj(src)
            print(data)

        def handle_on_init():
            print("Init received :)")

        def handle_wake_up(data):
            parsed_data = pickle_string_to_obj(data)
            self.all_ids.add(parsed_data['id'])

            picked_data = obj_to_pickle_string(self.all_ids)
            self.lib.Write(picked_data, sys.getsizeof(picked_data), OP_CLIENT_LIST_UPDATE)

        def handle_client_evict(data):
            evicted_peer = data.decode("utf-8")[:8]
            self.all_ids.remove(evicted_peer)

        def handle_self_up(data):
            self.cid = data.decode("utf-8")
            self.all_ids.add(self.cid)

        def handle_client_list_update(data):
            parsed_data = pickle_string_to_obj(data)
            self.all_ids = self.all_ids.union(parsed_data)

        global on_init_cb
        on_init_cb = FUNC(handle_on_init)
        self.lib.Register_callback("on_init".encode('utf-8'), on_init_cb)

        global on_recv_cb
        on_recv_cb = FUNC(on_recv)
        self.lib.Register_callback("on_recv".encode('utf-8'), on_recv_cb)

        global on_wakeup_cb
        on_wakeup_cb = FUNC(handle_wake_up)
        self.lib.Register_callback("on_wakeup".encode('utf-8'), on_wakeup_cb)

        global on_client_evict_cb
        on_client_evict_cb = FUNC(handle_client_evict)
        self.lib.Register_callback("on_clientevict".encode("utf-8"), on_client_evict_cb)

        global on_self_up_cb
        on_self_up_cb = FUNC(handle_self_up)
        self.lib.Register_callback("on_self_up".encode("utf-8"), on_self_up_cb)

        global on_client_list_update_cb
        on_client_list_update_cb = FUNC(handle_client_list_update)
        self.lib.Register_callback("on_client_list_update".encode("utf-8"), on_client_list_update_cb)

        # global on_client_ready
        # on_client_ready = FUNC(handle_client_ready)
        # fnname = "on_clientready"
        # self.lib.Register_callback(fnname.encode('utf-8'), on_client_ready)
        #
        # global on_client_update
        # onclientupdate = FUNC(handle_client_update)
        # fnname = "on_clientupdate"
        # self.lib.Register_callback(fnname.encode('utf-8'), onclientupdate)
        #
        # global onclienteval
        # onclienteval = FUNC(handle_client_eval)
        # fnname = "on_clienteval"
        # self.lib.Register_callback(fnname.encode('utf-8'), onclienteval)

    def join_existing_network(self):
        self.lib.Bootstrapping(self.bootstrap_address.encode('utf-8'))
        data = {
            'opcode': 'client_wake_up',
            'id': self.cid
        }
        sdata = obj_to_pickle_string(data)
        self.lib.Write(sdata, sys.getsizeof(sdata), OP_CLIENT_WAKE_UP)

    def start(self):
        self.lib.Init_p2p(self.host.encode('utf-8'), int(self.port))
        if self.bootstrap_address:
            self.join_existing_network()

        print("\n===============================================================\n")
        self.lib.Input()


if __name__ == '__main__':
    if len(sys.argv) == 3:
        print("Starting node sans bootstrap. "
              "Please connect other nodes with bootstrap addr {}:{}"
              .format(sys.argv[1], sys.argv[2]))
        peer = FLPeer(sys.argv[1], sys.argv[2])
    else:
        print("Starting the peer and connecting it to the P2P network.")
        peer = FLPeer(sys.argv[1], sys.argv[2], sys.argv[3])

    peer.start()
