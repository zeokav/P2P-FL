import gc
import sys
import threading
import time
import datetime
import logging
import os
import json
from ctypes import cdll
import ctypes
from helper import *

from keras.models import Sequential
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv2D, MaxPooling2D
import tensorflow.keras as keras

# gc.disable()
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


def storeData(fname, data):
    # Its important to use binary mode
    datafile = open(fname, 'wb+')
    # source, destination
    pickle.dump(data, datafile)
    datafile.close()

def loadData(fname):
    datafile = open(fname, 'rb')
    db = pickle.load(datafile)
    datafile.close()
    return db


class FLPeer:
    MAX_DATASET_SIZE_KEPT = 1200
    def __init__(self, global_model, host, port, bootstrap_address=None):
        self.all_ids = set()
        self.sorted_ids = []
        self.first_time = 1
        self.cid = None
        self.shut_down = False
        self.is_training = False
        self.current_round_client_updates = []
        self.round_counter = {}

        self.lib = cdll.LoadLibrary('./libp2p.so')
        self.lib.Init_p2p.restype = ctypes.c_char_p
        self.lib.Write.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_byte]
        self.bootstrap_address = bootstrap_address

        self.host = host
        self.port = port

        self.register_handles()

        self.stat_printer = threading.Thread(target=self.print_stats)
        #self.stat_printer.start()

        self.p2p_trainer = threading.Thread(target=self.run_trainer)
        self.p2p_trainer.start()

        self.global_model = global_model()
        import uuid
        self.model_id = str(uuid.uuid4())
        #self.init_model_config()
        import datasource
        self.train_loss = None
        self.train_accuracy = None
        self.datasource = (datasource.Cifar10)()
        
        
    def on_init(self, data):
            model_config = pickle_string_to_obj(data)
            
            if os.path.exists("fake_data") and os.path.exists("my_class_distr"):
                fake_data = loadData("fake_data")
                my_class_distr = loadData("my_class_distr")
            else:
                fake_data, my_class_distr = self.datasource.fake_non_iid_data(
                    min_train=model_config['min_train_size'],
                    max_train=FLPeer.MAX_DATASET_SIZE_KEPT,
                    data_split=model_config['data_split']
                )
                storeData("fake_data",fake_data)
                storeData("my_class_distr",my_class_distr)

            self.local_model = LocalModel(model_config, fake_data)

    def run_trainer(self):
        while not self.shut_down:
            if len(self.all_ids) >= 6 and self.sorted_ids[0] == self.cid and not self.is_training:
                print("Initializing training on: ", self.cid)
                metadata = {
                    "op": "request_update",
                    "round": 1,
                    'model_json': self.global_model.model.to_json(),
                    'model_id': self.model_id,
                    'min_train_size': 1200,
                    'data_split': (0.6, 0.3, 0.1), # train, test, valid
                    'epoch_per_round': 4,
                    'batch_size': 10,
                    'weights': self.global_model.current_weights
                }
                metadata_str = obj_to_pickle_string(metadata)

                self.on_init(metadata_str)
                
                '''
                for layer in self.local_model.model.layers:
                    print("Local Model***************Layer Weight : ", [np.std(x) for x in layer.get_weights()])
                '''
                self.lib.Write(metadata_str, sys.getsizeof(metadata_str), OP_REQUEST_UPDATE)

                self.is_training = True

                storeData("node_list", self.sorted_ids)

            time.sleep(1)

    def print_stats(self):
        while not self.shut_down:
            print("\n[{}]"
                  "\n\tID: {}"
                  "\n\tPeer list: {}"
                  "\n\tSelf index: {}"
                  "\n\tTraining: {}".format(datetime.datetime.now(), self.cid, self.all_ids,
                                            self.sorted_ids.index(self.cid) if self.cid else "",
                                            self.is_training))
            time.sleep(10)

    def update_for_round(self, tree_round):
        self_idx = self.sorted_ids.index(self.cid)
	
        round_parent_indices = [index for index in range(len(self.all_ids)) if index % (4 ** tree_round) == 0]

        if self_idx in round_parent_indices:
            # This is the parent, it just waits for other nodes to send their weights
            print("This is a parent, waiting for other nodes to send their data")
            self.is_training = True

        else:
            if self_idx % (4 ** (tree_round - 1)) != 0:
                print("Not participating in round {}".format(tree_round))
                return
            else:
                parent_idx = (self_idx // (4 ** tree_round)) * (4 ** tree_round)
                print("Self ID: {}, sending weights to parent: {}".format(self_idx, parent_idx))

                my_weights, t_loss, t_accuracy = self.local_model.train_one_round()
                metadata = {
                    "mode": "send_to_leader",
                    "target_bucket_peer_id": self.sorted_ids[parent_idx],
                    "weights": my_weights,
                    "round": tree_round,
                    "train_size": self.local_model.x_train.shape[0],
                    "valid_size": self.local_model.x_valid.shape[0],
                    "train_loss": t_loss,
                    "train_accuracy": t_accuracy
                }

                data_str = obj_to_pickle_string(metadata)
                self.lib.Write(data_str, sys.getsizeof(data_str), OP_CLIENT_UPDATE)

    def process_and_clear(self, targets, for_round):
        print("{} : Processing weight information".format(self.cid))
        print("Aggregating Weights for {} nodes".format(len(self.current_round_client_updates)))
        self.global_model.update_weights(
                        [x['weights'] for x in self.current_round_client_updates],
                        [x['train_size'] for x in self.current_round_client_updates],
                    )
        aggr_train_loss, aggr_train_accuracy = self.global_model.aggregate_train_loss_accuracy(
            [x['train_loss'] for x in self.current_round_client_updates],
            [x['train_accuracy'] for x in self.current_round_client_updates],
            [x['train_size'] for x in self.current_round_client_updates],
            for_round
        )
        if 'valid_loss' in self.current_round_client_updates[0]:
            aggr_valid_loss, aggr_valid_accuracy = self.global_model.aggregate_valid_loss_accuracy(
                [x['valid_loss'] for x in self.current_round_client_updates],
                [x['valid_accuracy'] for x in self.current_round_client_updates],
                [x['valid_size'] for x in self.current_round_client_updates],
                for_round
            )

        data = {
            "mode": "send_to_children",
            "targets": targets,
            "round": for_round,
            "weights": self.global_model.current_weights
        }
        data_str = obj_to_pickle_string(data)
        self.lib.Write(data_str, sys.getsizeof(data_str), OP_CLIENT_UPDATE)

        if self.sorted_ids[0] == self.cid:
            curr_count = self.round_counter.get(for_round, 0)
            self.round_counter[for_round] = curr_count + min(3, (len(self.sorted_ids) // (4 ** (for_round-1))))
            self.do_leader_round_completion_check(for_round)
        else:
            self.is_training = False
            self.current_round_client_updates = []

    def do_leader_round_completion_check(self, curr_round):
        curr_count = self.round_counter.get(curr_round)
        completion_count = (len(self.sorted_ids) // (4 ** (curr_round - 1))) \
                           - (len(self.sorted_ids) // (4 ** curr_round)) - 1

        print("Received ack from child for round {}, total required: {}. Round count: {}"
              .format(curr_round, completion_count, self.round_counter))

        if completion_count <= curr_count:
            print("Received update ack from all children. ")
            # There can be more rounds
            if completion_count != 0:
                print("Initiating the next round.")
                metadata = {
                    "op": "request_update",
                    "round": curr_round + 1
                }
                metadata_str = obj_to_pickle_string(metadata)
                self.lib.Write(metadata_str,
                               sys.getsizeof(metadata_str),
                               OP_REQUEST_UPDATE)

            # We've exhausted all rounds, we can reset the global leader
            else:
                print("No more rounds left.")
                self.is_training = False
                self.current_round_client_updates = []
                self.round_counter = {}

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
            try:
                self.cid = data.decode("utf-8")[:8]
            except Exception as e:
                print("Failed to start node, quitting", e)
                os.kill(os.getpid(), 9)
            self.sorted_ids = [self.cid]
            self.all_ids.add(self.cid)

        def handle_client_list_update(data):
            parsed_data = pickle_string_to_obj(data)
            self.all_ids = self.all_ids.union(parsed_data)
            self.sorted_ids = sorted(self.all_ids)

        def handle_update_request(data):
            parsed_data = pickle_string_to_obj(data)
            if self.first_time == 1:
                self.first_time = 0
                self.on_init(data)

            if parsed_data['round']==1:
                weights = parsed_data['weights']
                self.local_model.set_weights(weights)
            self.update_for_round(parsed_data['round'])

        def handle_client_update(data):
            parsed_data = pickle_string_to_obj(data)
            # We only care if the update is targeted to us.
            if parsed_data.get('mode') == "send_to_leader":
                if not parsed_data.get('target_bucket_peer_id') == self.cid:
                    return

                self.current_round_client_updates.append(parsed_data)

                self_idx = self.sorted_ids.index(self.cid)
                targets = self.sorted_ids[self_idx::(4 ** (parsed_data['round'] - 1))]
                expected_weights = min(len(targets)-1, 3)

                if len(self.current_round_client_updates) >= expected_weights:
                    self.local_model.set_weights(self.global_model.current_weights)
                    my_weights, t_loss, t_accuracy = self.local_model.train_one_round()
                    metadata = {
                        "mode": "send_to_leader",
                        "target_bucket_peer_id": self.cid,
                        "weights": my_weights,
                        "round": 0,
                        "train_size": self.local_model.x_train.shape[0],
                        "valid_size": self.local_model.x_valid.shape[0],
                        "train_loss": t_loss,
                        "train_accuracy": t_accuracy
                    }
                    self.current_round_client_updates.append(metadata)
                    self.process_and_clear(targets[self_idx:expected_weights], parsed_data['round'])

            elif parsed_data.get('mode') == "send_to_children": 
                if self.sorted_ids[0] == self.cid:
                    curr_round = parsed_data['round']
                    curr_count = self.round_counter.get(curr_round, 0)
                    self.round_counter[curr_round] = curr_count + 1
                    self.do_leader_round_completion_check(curr_round)

                if self.cid not in parsed_data.get('targets', []):
                    return
                else:
                    print("Updating model received from parent!")
                    weights = parsed_data['weights']
                    self.local_model.set_weights(weights)
                    #CreateModelFile("model_weights", self.global_model)


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

'''
**********************************************************************************************
'''
class GlobalModel(object):
    """docstring for GlobalModel"""
    def __init__(self):
        self.model = self.build_model()
        self.current_weights = self.model.get_weights()
        # for convergence check
        self.prev_train_loss = None

        # all rounds; losses[i] = [round#, timestamp, loss]
        # round# could be None if not applicable
        self.train_losses = []
        self.valid_losses = []
        self.train_accuracies = []
        self.valid_accuracies = []

        self.training_start_time = int(round(time.time()))

    def build_model(self):
        raise NotImplementedError()

    def get_weights(self):
        return self.current_weights

    # client_updates = [(   w, n)..]
    def update_weights(self, client_weights, client_sizes):
        import numpy as np
        new_weights = [np.zeros(w.shape) for w in self.current_weights]
        total_size = np.sum(client_sizes)

        for c in range(len(client_weights)):
            for i in range(len(new_weights)):
                new_weights[i] += client_weights[c][i] * client_sizes[c] / total_size
        self.current_weights = new_weights

    def aggregate_loss_accuracy(self, client_losses, client_accuracies, client_sizes):
        import numpy as np
        total_size = np.sum(client_sizes)
        # weighted sum
        aggr_loss = np.sum(client_losses[i] / total_size * client_sizes[i]
                for i in range(len(client_sizes)))
        aggr_accuraries = np.sum(client_accuracies[i] / total_size * client_sizes[i]
                for i in range(len(client_sizes)))
        return aggr_loss, aggr_accuraries

    # cur_round coule be None
    def aggregate_train_loss_accuracy(self, client_losses, client_accuracies, client_sizes, cur_round):
        cur_time = int(round(time.time())) - self.training_start_time
        aggr_loss, aggr_accuraries = self.aggregate_loss_accuracy(client_losses, client_accuracies, client_sizes)
        self.train_losses += [[cur_round, cur_time, aggr_loss]]
        self.train_accuracies += [[cur_round, cur_time, aggr_accuraries]]
        with open('stats.txt', 'w') as outfile:
            json.dump(self.get_stats(), outfile)
        return aggr_loss, aggr_accuraries

    # cur_round coule be None
    def aggregate_valid_loss_accuracy(self, client_losses, client_accuracies, client_sizes, cur_round):
        cur_time = int(round(time.time())) - self.training_start_time
        aggr_loss, aggr_accuraries = self.aggregate_loss_accuracy(client_losses, client_accuracies, client_sizes)
        self.valid_losses += [[cur_round, cur_time, aggr_loss]]
        self.valid_accuracies += [[cur_round, cur_time, aggr_accuraries]]
        with open('stats.txt', 'w') as outfile:
            json.dump(self.get_stats(), outfile)
        return aggr_loss, aggr_accuraries

    def get_stats(self):
        return {
            "train_loss": self.train_losses,
            "valid_loss": self.valid_losses,
            "train_accuracy": self.train_accuracies,
            "valid_accuracy": self.valid_accuracies
        }


class GlobalModel_CIFAR10_initial(GlobalModel):
    def __init__(self):
        super(GlobalModel_CIFAR10_initial, self).__init__()

    def build_model(self):
        # ~5MB worth of parameters
        from keras.models import Sequential
        from keras.layers import Dense, Dropout, Flatten
        from keras.layers import Conv2D, MaxPooling2D

        model = Sequential()
        model.add(Conv2D(32, (3, 3), activation='relu', kernel_initializer='he_uniform', padding='same', input_shape=(32, 32, 3)))
        model.add(Conv2D(32, (3, 3), activation='relu', kernel_initializer='he_uniform', padding='same'))
        model.add(MaxPooling2D((2, 2)))
        model.add(Dropout(0.2))
        model.add(Conv2D(64, (3, 3), activation='relu', kernel_initializer='he_uniform', padding='same'))
        model.add(Conv2D(64, (3, 3), activation='relu', kernel_initializer='he_uniform', padding='same'))
        model.add(MaxPooling2D((2, 2)))
        model.add(Dropout(0.2))
        model.add(Conv2D(128, (3, 3), activation='relu', kernel_initializer='he_uniform', padding='same'))
        model.add(Conv2D(128, (3, 3), activation='relu', kernel_initializer='he_uniform', padding='same'))
        model.add(MaxPooling2D((2, 2)))
        model.add(Dropout(0.2))
        model.add(Flatten())
        model.add(Dense(128, activation='relu', kernel_initializer='he_uniform'))
        model.add(Dropout(0.2))
        model.add(Dense(10, activation='softmax'))
        print(model)
        # """
        import tensorflow.keras as keras
        model.compile(loss=keras.losses.categorical_crossentropy,
                      optimizer=keras.optimizers.Adadelta(),
                      metrics=['accuracy'])
        return model

#Training Data Locally at the peer
class LocalModel(object):
    def __init__(self, model_config, data_collected):
        # model_config:
            # 'model': self.global_model.model.to_json(),
            # 'model_id'
            # 'min_train_size'
            # 'data_split': (0.6, 0.3, 0.1), # train, test, valid
            # 'epoch_per_round'
            # 'batch_size'
        self.model_config = model_config

        from keras.models import model_from_json
        self.model = model_from_json(model_config['model_json'])
        # the weights will be initialized on first pull from server

        import tensorflow.keras as keras
        self.model.compile(loss=keras.losses.categorical_crossentropy,
              optimizer=keras.optimizers.Adadelta(),
              metrics=['accuracy'])

        train_data, test_data, valid_data = data_collected
        import numpy as np
        self.x_train = np.array([tup[0] for tup in train_data])
        self.y_train = np.array([tup[1] for tup in train_data])
        self.x_test = np.array([tup[0] for tup in test_data])
        self.y_test = np.array([tup[1] for tup in test_data])
        self.x_valid = np.array([tup[0] for tup in valid_data])
        self.y_valid = np.array([tup[1] for tup in valid_data])

    def get_weights(self):
        return self.model.get_weights()

    def set_weights(self, new_weights):
        self.model.set_weights(new_weights)

    # return final weights, train loss, train accuracy
    def train_one_round(self):
        import tensorflow.keras as keras
        import numpy as np
        self.model.compile(loss=keras.losses.categorical_crossentropy,
              optimizer=keras.optimizers.Adadelta(),
              metrics=['accuracy'])
        
        self.model.fit(self.x_train, self.y_train,
                  epochs=self.model_config['epoch_per_round'],
                  batch_size=self.model_config['batch_size'],
                  verbose=1,
                  validation_data=(self.x_valid, self.y_valid))

        score = self.model.evaluate(self.x_train, self.y_train, verbose=0)
        print('Train loss:', score[0])
        print('Train accuracy:', score[1])
        # Store model here
        return self.model.get_weights(), score[0], score[1]

    def validate(self):
        score = self.model.evaluate(self.x_valid, self.y_valid, verbose=0)
        print('Validate loss:', score[0])
        print('Validate accuracy:', score[1])
        return score

    def evaluate(self):
        score = self.model.evaluate(self.x_test, self.y_test, verbose=0)
        print('Test loss:', score[0])
        print('Test accuracy:', score[1])
        return score

'''
***********************************************************************************
'''


if __name__ == '__main__':
    if len(sys.argv) == 3:
        print("Starting node sans bootstrap. "
              "Please connect other nodes with bootstrap addr {}:{}"
              .format(sys.argv[1], sys.argv[2]))
        peer = FLPeer(GlobalModel_CIFAR10_initial, sys.argv[1], sys.argv[2])
    else:
        print("Starting the peer and connecting it to the P2P network.")
        peer = FLPeer(GlobalModel_CIFAR10_initial, sys.argv[1], sys.argv[2], sys.argv[3])

    peer.start()
