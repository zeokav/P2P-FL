#import uuid
#import numpy as np
#import keras
#from keras.models import Sequential
#from keras.layers import Dense, Dropout, Flatten
#from keras.layers import Conv2D, MaxPooling2D
#from keras import backend as K
import gc
gc.disable()
#import base64

import random
import json
import sys
import time
import datetime

import logging
default_logger = logging.getLogger('tunnel.logger')
default_logger.setLevel(logging.CRITICAL)
default_logger.disabled = False

from ctypes import cdll
import ctypes

import pickle

FUNC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)

#to server
OP_RECV                      = 0x00
OP_CLIENT_WAKE_UP            = 0x01
OP_CLIENT_READY              = 0x02
OP_CLIENT_UPDATE             = 0x03
OP_CLIENT_EVAL               = 0x04
#to client
OP_INIT                      = 0x05
OP_REQUEST_UPDATE            = 0x06
OP_STOP_AND_EVAL             = 0x07

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

class GlobalModel_CIFAR10_initial(GlobalModel):
    def __init__(self):
        super(GlobalModel_CIFAR10_initial, self).__init__()

    def build_model(self):
        # ~5MB worth of parameters
        from keras.models import Sequential
        from keras.layers import Dense, Dropout, Flatten
        from keras.layers import Conv2D, MaxPooling2D
        """
        model = Sequential()
        model.add(Conv2D(32, kernel_size=(3, 3),
                          activation='relu',
                          input_shape=(32, 32, 3)))
        model.add(Conv2D(64, (3, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))
        model.add(Flatten())
        model.add(Dense(128, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(10, activation='softmax'))
        
        """
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
        
######## Flask server with Socket IO ########

# Federated Averaging algorithm with the server pulling from clients

class FLServer(object):
    
    MIN_NUM_WORKERS = 2
    MAX_NUM_ROUNDS = 10
    NUM_CLIENTS_CONTACTED_PER_ROUND = 1
    ROUNDS_BETWEEN_VALIDATIONS = 2

    def __init__(self, global_model, host, port):
        self.global_model = global_model()

        self.ready_client_sids = set()

        self.lib = cdll.LoadLibrary('./libp2p.so')
        self.lib.Init_p2p.restype = ctypes.c_char_p
        self.lib.Write.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_byte]

        self.host = host
        self.port = port
        import uuid
        self.model_id = str(uuid.uuid4())

        #####
        # training states
        self.current_round = -1  # -1 for not yet started
        self.current_round_client_updates = []
        self.eval_client_updates = []
        #####

        # socket io messages
        self.register_handles()
        
    def register_handles(self):

        def on_recv(src):
            print("on_recv : ")
            data = pickle_string_to_obj(src)
            if data['opcode'] == "client_wake_up":
                handle_wake_up(data)
            if data['opcode'] == "client_ready":
                handle_client_ready(data)
            if data['opcode'] == "client_update":
                handle_client_update(data)
            if data['opcode'] == "client_eval":
                handle_client_eval(data)

        def handle_connect():
            filehandle = open("helloworld.txt", "a")
            filehandle.write("connected\n")
            filehandle.close()

        def handle_reconnect():
            filehandle = open("helloworld.txt", "a")
            filehandle.write("reconnected\n")
            filehandle.close()

        def handle_reconnect():
            filehandle = open("helloworld.txt", "a")
            filehandle.write("disconnected\n")
            filehandle.close()
            if request.sid in self.ready_client_sids:
                self.ready_client_sids.remove(request.sid)


        def handle_wake_up(data):
            print("on_client_wake_up")
            data = pickle_string_to_obj(data)
            filehandle = open("helloworld.txt", "a")
            filehandle.write("client wake_up: \n")
            filehandle.close()

            metadata = {
                'opcode' : "init",
                'model_json': self.global_model.model.to_json(),
                'model_id': self.model_id,
                'min_train_size': 1200,
                'data_split': (0.6, 0.3, 0.1), # train, test, valid
                'epoch_per_round': 1,
                'batch_size': 10
            }
            sdata = obj_to_pickle_string(metadata)
            self.lib.Write(sdata, sys.getsizeof(sdata),OP_INIT)


        def handle_client_ready(data):
            print("on_client_ready")
            data = pickle_string_to_obj(data)
            filehandle = open("helloworld.txt", "a")
            filehandle.write("client ready for training\n")
            filehandle.close()

            print(data['cid'])
            self.ready_client_sids.add(data['cid'])

            if len(self.ready_client_sids) >= FLServer.MIN_NUM_WORKERS and self.current_round == -1:
                filehandle = open("helloworld.txt", "a")
                global start
                start = datetime.datetime.now()
                filehandle.writelines("start : " + str(start)+str("\n"))
                filehandle.close()
                self.train_next_round()
            else:
                filehandle = open("helloworld.txt", "a")
                filehandle.writelines("client_ready out\n")
                filehandle.close()


        def handle_client_update(data):
            print("on_client_update")
            data = pickle_string_to_obj(data)
            filehandle = open("helloworld.txt", "a")
            filehandle.write("handle client_update"+str(data['cid'])+str("\n"))
            filehandle.close()
            for x in data:
                if x != 'weights':
                    print(x, data[x])
            # data:
            #   weights
            #   train_size
            #   valid_size
            #   train_loss
            #   train_accuracy
            #   valid_loss?
            #   valid_accuracy?

            # discard outdated update
            print('round_number', self.current_round, data['round_number'])
            if data['round_number'] == self.current_round:
                self.current_round_client_updates += [data]
                self.current_round_client_updates[-1]['weights'] = pickle_string_to_obj(data['weights'])
                
                # tolerate 30% unresponsive clients
                if len(self.current_round_client_updates) > FLServer.NUM_CLIENTS_CONTACTED_PER_ROUND * .7:
                    self.global_model.update_weights(
                        [x['weights'] for x in self.current_round_client_updates],
                        [x['train_size'] for x in self.current_round_client_updates],
                    )
                    aggr_train_loss, aggr_train_accuracy = self.global_model.aggregate_train_loss_accuracy(
                        [x['train_loss'] for x in self.current_round_client_updates],
                        [x['train_accuracy'] for x in self.current_round_client_updates],
                        [x['train_size'] for x in self.current_round_client_updates],
                        self.current_round
                    )

                    filehandle = open("helloworld.txt", "a")
                    filehandle.write("aggr_train_loss"+str(aggr_train_loss)+str("\n"))
                    filehandle.write("aggr_train_accuracy"+str(aggr_train_accuracy)+str("\n"))
                    filehandle.close()

                    if 'valid_loss' in self.current_round_client_updates[0]:
                        aggr_valid_loss, aggr_valid_accuracy = self.global_model.aggregate_valid_loss_accuracy(
                            [x['valid_loss'] for x in self.current_round_client_updates],
                            [x['valid_accuracy'] for x in self.current_round_client_updates],
                            [x['valid_size'] for x in self.current_round_client_updates],
                            self.current_round
                        )
                        filehandle = open("helloworld.txt", "a")
                        filehandle.write("aggr_valid_loss"+str(aggr_valid_loss)+str("\n"))
                        filehandle.write("aggr_valid_accuracy"+str(aggr_valid_accuracy)+str("\n"))
                        filehandle.close()

                    if self.global_model.prev_train_loss is not None and \
                            (self.global_model.prev_train_loss - aggr_train_loss) / self.global_model.prev_train_loss < .01:
                        # converges
                        filehandle = open("helloworld.txt", "a")
                        filehandle.write("converges! starting test phase..")
                        filehandle.close()
                        self.stop_and_eval()
                        return
                    
                    self.global_model.prev_train_loss = aggr_train_loss

                    if self.current_round >= FLServer.MAX_NUM_ROUNDS:
                        self.stop_and_eval()
                    else:
                        self.train_next_round()

        def handle_client_eval(data):
            print("on_client_eval")
            data = pickle_string_to_obj(data)
            del data['cid']

            if self.eval_client_updates is None:
                return
            #filehandle = open("helloworld.txt", "a")
            #filehandle.write("handle client_eval"+str(rmsg.sid)+str("\n"))
            #filehandle.close()
            self.eval_client_updates += [data] # data here should be without sid

            # tolerate 30% unresponsive clients
            if len(self.eval_client_updates) > FLServer.NUM_CLIENTS_CONTACTED_PER_ROUND * .7:
                aggr_test_loss, aggr_test_accuracy = self.global_model.aggregate_loss_accuracy(
                    [x['test_loss'] for x in self.eval_client_updates],
                    [x['test_accuracy'] for x in self.eval_client_updates],
                    [x['test_size'] for x in self.eval_client_updates],
                );
                filehandle = open("helloworld.txt", "a")
                filehandle.write("\naggr_test_loss"+str(aggr_test_loss)+str("\n"))
                filehandle.write("aggr_test_accuracy"+str(aggr_test_accuracy)+str("\n"))
                filehandle.write("== done ==\n")
                end = datetime.datetime.now()
                diff = end - start
                filehandle.writelines("end : " + str(end)+str("\n"))
                filehandle.writelines("diff(s) : " + str(diff.seconds)+str("\n"))
                filehandle.writelines("diff(us) : " + str(diff.microseconds)+str("\n"))
                filehandle.close()
                self.eval_client_updates = None  # special value, forbid evaling again

        global onrecv
        #onrecv = FUNC(on_recv)
        #fnname="on_recv"
        #self.lib.Register_callback(fnname.encode('utf-8'),onrecv)

        global onwakeup
        onwakeup = FUNC(handle_wake_up)
        fnname="on_wakeup"
        self.lib.Register_callback(fnname.encode('utf-8'),onwakeup)

        global onclientready
        onclientready = FUNC(handle_client_ready)
        fnname="on_clientready"
        self.lib.Register_callback(fnname.encode('utf-8'),onclientready)

        global onclientupdate
        onclientupdate = FUNC(handle_client_update)
        fnname="on_clientupdate"
        self.lib.Register_callback(fnname.encode('utf-8'),onclientupdate)

        global onclienteval
        onclienteval = FUNC(handle_client_eval)
        fnname="on_clienteval"
        self.lib.Register_callback(fnname.encode('utf-8'),onclienteval)

    # Note: we assume that during training the #workers will be >= MIN_NUM_WORKERS
    def train_next_round(self):
        print("train_next_round\n")
        self.current_round += 1
        # buffers all client updates
        self.current_round_client_updates = []

        filehandle = open("helloworld.txt", "a")
        filehandle.write("### Round "+str(self.current_round)+"###\n")
        client_sids_selected = random.sample(list(self.ready_client_sids), FLServer.NUM_CLIENTS_CONTACTED_PER_ROUND)
        filehandle.write("request updates to "+str(client_sids_selected)+str("\n"))
        filehandle.close()

        metadata = {
                'opcode': "request_update",
                'model_id': self.model_id,
                'round_number': self.current_round,
                'current_weights': obj_to_pickle_string(self.global_model.current_weights),
                'run_validation': self.current_round % FLServer.ROUNDS_BETWEEN_VALIDATIONS == 0
        }
        sdata = obj_to_pickle_string(metadata)
        self.lib.Write(sdata, sys.getsizeof(sdata), OP_REQUEST_UPDATE)
        print("request_update sent\n")

    
    def stop_and_eval(self):
        self.eval_client_updates = []
        metadata = {
                'opcode': "stop_and_eval",
                'model_id': self.model_id,
                'current_weights': obj_to_pickle_string(self.global_model.current_weights)
        }
        sdata = obj_to_pickle_string(metadata)
        self.lib.Write(sdata, sys.getsizeof(sdata), OP_STOP_AND_EVAL)

    def start(self):
        self.lib.Init_p2p(self.host.encode('utf-8'),int(self.port))
        self.lib.Input()



def obj_to_pickle_string(x):
    import base64
    return base64.b64encode(pickle.dumps(x))

def pickle_string_to_obj(s):
    import base64
    return pickle.loads(base64.b64decode(s))

if __name__ == '__main__':
    #server = FLServer(GlobalModel_MNIST_CNN, "127.0.0.1", 9004)
    server = FLServer(GlobalModel_CIFAR10_initial, sys.argv[1], sys.argv[2])
    filehandle = open("helloworld.txt", "w")
    filehandle.write("listening on " + str(sys.argv[1]) + ":" + str(sys.argv[2]) + "\n");
    filehandle.close()
    server.start()
