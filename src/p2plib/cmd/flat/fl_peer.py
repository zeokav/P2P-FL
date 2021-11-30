import gc
import sys
import threading
import time
import datetime
import logging
import os

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

def storeData(fname, data):
    # Its important to use binary mode
    datafile = open(fname, 'ab')
    # source, destination
    pickle.dump(data, datafile)
    datafile.close()

def loadData(fname):
    datafile = open(fname, 'rb')
    db = pickle.load(datafile)
    datafile.close()
    return db


class FLPeer:
    def __init__(self, global_model, host, port, bootstrap_address=None):
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


        self.global_model = global_model()
        import uuid
        self.model_id = str(uuid.uuid4())
        self.init_model_config()


        self.local_training = threading.Thread(target=self.run_local_training)
        self.local_training.start()


    def init_model_config(self):

        import datasource
        self.datasource = (datasource.Mnist)()
        self.train_loss = None
        self.train_accuracy = None

        model_config = {
                        'opcode' : "init",
                        'model_json': self.global_model.model.to_json(),
                        'model_id': self.model_id,
                        'min_train_size': 1200,
                        'data_split': (0.6, 0.3, 0.1), # train, test, valid
                        'epoch_per_round': 1,
                        'batch_size': 10
                    }

        if os.path.exists("fake_data") and os.path.exists("my_class_distr"):
                fake_data = loadData("fake_data")
                my_class_distr = loadData("my_class_distr")
        else:
            fake_data, my_class_distr = self.datasource.fake_non_iid_data(
                min_train=model_config['min_train_size'],
                max_train=FederatedClient.MAX_DATASET_SIZE_KEPT,
                data_split=model_config['data_split']
            )
            storeData("fake_data",fake_data)
            storeData("my_class_distr",my_class_distr)

        self.local_model = LocalModel(model_config, fake_data)

    def run_local_training(self):
        while not self.shut_down:
            my_weights, self.train_loss, self.train_accuracy = self.local_model.train_one_round()
            print("\n Train Loss : {}, Train accuracy : {}".format(self.train_loss, self.train_accuracy))

            time.sleep(60)

    def run_trainer(self):
        while not self.shut_down:
            if len(self.all_ids) >= 6 and self.sorted_ids[0] == self.cid and not self.is_training:
                print("Initializing training on: ", self.cid)
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

    # client_updates = [(w, n)..]
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


class GlobalModel_MNIST_CNN(GlobalModel):
    def __init__(self):
        super(GlobalModel_MNIST_CNN, self).__init__()

    def build_model(self):
        # ~5MB worth of parameters
        from keras.models import Sequential
        from keras.layers import Dense, Dropout, Flatten
        from keras.layers import Conv2D, MaxPooling2D
        model = Sequential()
        model.add(Conv2D(32, kernel_size=(3, 3),
                         activation='relu',
                         input_shape=(28, 28, 1)))
        model.add(Conv2D(64, (3, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))
        model.add(Flatten())
        model.add(Dense(128, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(10, activation='softmax'))

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
        peer = FLPeer(GlobalModel_MNIST_CNN, sys.argv[1], sys.argv[2])
    else:
        print("Starting the peer and connecting it to the P2P network.")
        peer = FLPeer(GlobalModel_MNIST_CNN, sys.argv[1], sys.argv[2], sys.argv[3])

    peer.start()
