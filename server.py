import os
import cherrypy
from pyramid.paster import get_app, setup_logging

if __name__ == '__main__':
    # Construct the WSGI app
    ini_path = os.path.join(os.path.dirname(__file__), 'production.ini'))
    setup_logging(ini_path)
    app = get_app(ini_path, 'main')
    # Construct the server
    cherrypy.tree.graft(app, "/")
    cherrypy.server.unsubscribe()
    server = cherrypy._cpserver.Server()
    server.socket_host = "0.0.0.0"
    server.socket_port = 8080
    server.thread_pool = 30
    server.subscribe()
    cherrypy.engine.start()
    cherrypy.engine.block()

