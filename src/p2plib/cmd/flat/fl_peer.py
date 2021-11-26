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
on_request_update_cb = None
on_client_update_cb = None


class FLPeer:
    def __init__(self, host, port, bootstrap_address=None):
        self.all_ids = set()
        self.sorted_ids = []

        self.cid = None
        self.shut_down = False
        self.is_training = False
        self.collected_weights = []

        self.lib = cdll.LoadLibrary('./libp2p.so')
        self.lib.Init_p2p.restype = ctypes.c_char_p
        self.lib.Write.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_byte]
        self.bootstrap_address = bootstrap_address

        self.host = host
        self.port = port

        self.register_handles()

        self.stat_printer = threading.Thread(target=self.print_stats)
        self.stat_printer.start()

        self.p2p_trainer = threading.Thread(target=self.run_trainer)
        self.p2p_trainer.start()

    def run_trainer(self):
        while not self.shut_down:
            if len(self.all_ids) > 3 and self.sorted_ids[0] == self.cid and not self.is_training:
                print("Initializer: ", self.cid)
                metadata = {
                    "op": "request_update",
                    "round": 1
                }
                metadata_str = obj_to_pickle_string(metadata)
                self.lib.Write(metadata_str, sys.getsizeof(metadata_str), OP_REQUEST_UPDATE)

                self.is_training = True

            time.sleep(5)

    def print_stats(self):
        while not self.shut_down:
            print("\n[{}]"
                  "\n\tID: {}"
                  "\n\tPeer list: {}"
                  "\n\tSelf index: {}"
                  "\n\tTraining: {}".format(datetime.datetime.now(), self.cid, self.all_ids,
                                            self.sorted_ids.index(self.cid) if self.cid else "",
                                            self.is_training))
            time.sleep(5)

    def update_for_round(self, tree_round):
        print("Update for round: ", tree_round)
        self_idx = self.sorted_ids.index(self.cid)

        round_parent_indices = [index for index in range(len(self.all_ids)) if index % (4 ** tree_round) == 0]

        if self_idx in round_parent_indices:
            # This is the parent, it just waits for other nodes to send their weights
            print("This is a parent")
            self.is_training = True

        else:
            if self_idx % (4 ** (tree_round - 1)) != 0:
                print("Not participating in round {}".format(tree_round))

            # self.model.get_weights()
            weights_data = {}
            metadata = {
                "mode": "send_to_leader",
                "target_bucket_peer_id": self.sorted_ids[self_idx // (4 ** tree_round)],
                "weights": weights_data,
                "round": tree_round
            }

            data_str = obj_to_pickle_string(metadata)
            self.lib.Write(data_str, sys.getsizeof(data_str), OP_CLIENT_UPDATE)

    def process_and_clear(self):
        print("{} Processing weight information".format(self.cid))
        self.is_training = False
        self.collected_weights = []

        weights_data = {}

        data = {
            "mode": "send_to_children",
            "targets": ["???"],
            "weights": weights_data
        }
        data_str = obj_to_pickle_string(data)
        self.lib.Write(data_str, sys.getsizeof(data_str), OP_CLIENT_UPDATE)

    def register_handles(self):
        def on_recv(src):
            print("On receive")
            data = pickle_string_to_obj(src)
            print(data)

        def handle_wake_up(data):
            parsed_data = pickle_string_to_obj(data)
            self.all_ids.add(parsed_data['id'])
            self.sorted_ids = sorted(self.all_ids)

            picked_data = obj_to_pickle_string(self.all_ids)
            self.lib.Write(picked_data, sys.getsizeof(picked_data), OP_CLIENT_LIST_UPDATE)

        def handle_client_evict(data):
            evicted_peer = data.decode("utf-8")[:8]
            self.all_ids.remove(evicted_peer)

        def handle_self_up(data):
            self.cid = data.decode("utf-8")[:8]
            self.sorted_ids = [self.cid]
            self.all_ids.add(self.cid)

        def handle_client_list_update(data):
            parsed_data = pickle_string_to_obj(data)
            self.all_ids = self.all_ids.union(parsed_data)
            self.sorted_ids = sorted(self.all_ids)

        def handle_update_request(data):
            parsed_data = pickle_string_to_obj(data)
            self.update_for_round(parsed_data['round'])

        def handle_client_update(data):
            parsed_data = pickle_string_to_obj(data)
            # We only care if the update is targeted to us.
            if parsed_data.get('mode') == "send_to_leader":
                if not parsed_data.get('target_bucket_peer_id') == self.cid:
                    return
                self.collected_weights.append(parsed_data.get('weights', []))
                expected_weights = len(
                    self.sorted_ids[self.sorted_ids.index(self.cid)::(4 ** (parsed_data['round'] - 1))]
                ) - 1

                if len(self.collected_weights) > min(expected_weights, 4):
                    self.process_and_clear()

            elif parsed_data.get('mode') == "send_to_children":
                # if self.cid not in parsed_data.get('targets', []):
                print("Ignoring update from parent")
                return

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

        global on_request_update_cb
        on_request_update_cb = FUNC(handle_update_request)
        self.lib.Register_callback("on_request_update".encode("utf-8"), on_request_update_cb)

        global on_client_update_cb
        on_client_update_cb = FUNC(handle_client_update)
        self.lib.Register_callback("on_clientupdate".encode("utf-8"), on_client_update_cb)

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
