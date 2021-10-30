#import numpy as np
#import uuid
#import keras
#from keras.models import model_from_json
#import datasource
import gc
gc.disable()
from fl_server import obj_to_pickle_string, pickle_string_to_obj
import os
import sys
import datetime
import pickle

from ctypes import cdll
import ctypes

client = None

FUNC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)

#server
OP_RECV                      = 0x00
OP_CLIENT_WAKE_UP            = 0x01
OP_CLIENT_READY              = 0x02
OP_CLIENT_UPDATE             = 0x03
OP_CLIENT_EVAL               = 0x04
#client
OP_INIT                      = 0x05
OP_REQUEST_UPDATE            = 0x06
OP_STOP_AND_EVAL             = 0x07
  
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


class FederatedClient(object):
    MAX_DATASET_SIZE_KEPT = 1200

    def __init__(self, host, port, bootaddr, datasource):
        self.local_model = None
        self.datasource = datasource()
        import uuid
        self.cid = str(uuid.uuid4())

        print("p2p init")
        self.lib = cdll.LoadLibrary('./libp2p.so')
        self.lib.Init_p2p.restype = ctypes.c_char_p
        self.lib.Write.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_byte]

        self.register_handles()

        self.lib.Init_p2p(host.encode('utf-8'),int(port))

        self.lib.Bootstrapping(bootaddr.encode('utf-8'))

        print("send client_wake_up")
        metadata = {
	    'cid' : self.cid,
            'opcode':"client_wake_up"
        }
        sdata = obj_to_pickle_string(metadata)
        self.lib.Write(sdata, sys.getsizeof(sdata), OP_CLIENT_WAKE_UP)
    
    def register_handles(self):

        def on_recv(src):
            print("on_recv : ")
            data = pickle_string_to_obj(src)
            if data['opcode'] == "init":
                on_init(data)
            elif data['opcode'] == "request_update":
                on_request_update(data)
            elif data['opcode'] == "stop_and_eval":
                on_stop_and_eval(data)
            else:
                print("unknown opcode ", data['opcode'])
	    
        def on_connect():
            print('connect')

        def on_disconnect():
            print('disconnect')

        def on_reconnect():
            print('reconnect')

        def on_init(data):
            print('on init')
            model_config = pickle_string_to_obj(data)
            print('preparing local data based on server model_config')

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

            metadata = {
	        'cid' : self.cid,
                'opcode':"client_ready",
                'train_size': self.local_model.x_train.shape[0],
                'class_distr': my_class_distr  # for debugging, not needed in practice
            }
            sdata = obj_to_pickle_string(metadata)
            self.lib.Write(sdata, sys.getsizeof(sdata), OP_CLIENT_READY)

        def on_request_update(data):
            print("on request update")
            data = pickle_string_to_obj(data)
            filehandle = open("helloworldclient.txt", "a")
            start = datetime.datetime.now()
            filehandle.writelines("start : " + str(start)+str("\n"))

            weights = pickle_string_to_obj(data['current_weights'])

            self.local_model.set_weights(weights)
            my_weights, train_loss, train_accuracy = self.local_model.train_one_round()
            resp = {
	        'cid' : self.cid,
                'opcode':"client_update",
                'round_number': data['round_number'],
                'weights': obj_to_pickle_string(my_weights),
                'train_size': self.local_model.x_train.shape[0],
                'valid_size': self.local_model.x_valid.shape[0],
                'train_loss': train_loss,
                'train_accuracy': train_accuracy,
            }
            if data['run_validation']:
                valid_loss, valid_accuracy = self.local_model.validate()
                resp['valid_loss'] = valid_loss
                resp['valid_accuracy'] = valid_accuracy

            end = datetime.datetime.now()
            diff = end - start
            filehandle.writelines("end : " + str(end)+str("\n"))
            filehandle.writelines("diff(s) : " + str(diff.seconds)+str("\n"))
            filehandle.writelines("diff(us) : " + str(diff.microseconds)+str("\n"))
            filehandle.close() 

            sdata = obj_to_pickle_string(resp)
            self.lib.Write(sdata, sys.getsizeof(sdata), OP_CLIENT_UPDATE)


        def on_stop_and_eval(data):
            data = pickle_string_to_obj(data)
            weights = pickle_string_to_obj(data['current_weights'])
            self.local_model.set_weights(weights)
            test_loss, test_accuracy = self.local_model.evaluate()
            resp = {
	        'cid' : self.cid,
                'opcode':"client_eval",
                'test_size': self.local_model.x_test.shape[0],
                'test_loss': test_loss,
                'test_accuracy': test_accuracy
            }
            sdata = obj_to_pickle_string(resp)
            self.lib.Write(sdata, sys.getsizeof(sdata), OP_CLIENT_EVAL)

        global onrecv
        #onrecv = FUNC(on_recv)
        #fnname="on_recv"
        #self.lib.Register_callback(fnname.encode('utf-8'),onrecv)

        global oninit
        oninit = FUNC(on_init)
        fnname="on_init"
        self.lib.Register_callback(fnname.encode('utf-8'),oninit)

        global onrequestupdate
        onrequestupdate = FUNC(on_request_update)
        fnname="on_request_update"
        self.lib.Register_callback(fnname.encode('utf-8'),onrequestupdate)

        global onstopandeval
        onstopandeval = FUNC(on_stop_and_eval)
        fnname="on_stop_and_eval"
        self.lib.Register_callback(fnname.encode('utf-8'),onstopandeval)

if __name__ == "__main__":
    filehandle = open("helloworldclient.txt", "w")
    filehandle.write("running client \n")
    filehandle.close()
    import datasource
    #client = FederatedClient("127.0.0.1", 9005, "127.0.0.1:9004", datasource.Mnist)
    client = FederatedClient(sys.argv[1], sys.argv[2], sys.argv[3], datasource.Mnist)
    client.lib.Input()
