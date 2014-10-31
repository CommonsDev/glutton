from pyramid.config import Configurator

import views

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)

    config.add_renderer(name='turtle', factory='glutton.renderers.TurtleRenderer')
    config.add_renderer(name='jsonld', factory='glutton.renderers.JSONLDRenderer')
    config.add_renderer(name='html', factory='glutton.renderers.HTMLRenderer')

    config.include('pyramid_chameleon')
    # config.include("cornice")

    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')

    # LDP
    config.add_route('rdfsource', r'/r{uri:.*}')
    #config.add_view(views.LDPRDFSourceResourceView, attr='get', request_method=('GET', 'HEAD', 'OPTIONS'))
    #config.add_view(views.LDPRDFSourceResourceView, attr='post', request_method=('POST',))

    config.scan()
    return config.make_wsgi_app()
