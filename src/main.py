import os
from http.server import HTTPServer, BaseHTTPRequestHandler

#import tensorflow_federated as tff


class Serv(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/test.html'
        try:
            file_to_open = open(self.path[1:]).read()
            self.send_response(200)
        except Exception as e:
            file_to_open = "File not found"
            self.send_response(404)
        self.end_headers()
        self.wfile.write(bytes(file_to_open, 'utf-8'))


#print(tff.federated_computation(lambda: 'TFF initialized')())
print("Starting server up on node: {}".format(os.getenv("NODE_ID")))

httpd = HTTPServer(('localhost', 8080), Serv)
httpd.serve_forever()
