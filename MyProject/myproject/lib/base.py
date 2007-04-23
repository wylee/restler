from pylons import Response, c, g, cache, request, session
from pylons.controllers import WSGIController
from pylons.decorators import jsonify, validate
from pylons.templating import render, render_response
from pylons.helpers import abort, redirect_to, etag_cache
from pylons.i18n import N_, _, ungettext

import myproject.models as model
import myproject.lib.helpers as h

import restler


class RestController(restler.BaseController(model)):
    def __call__(self, environ, start_response):
        return super(RestController, self).__call__(environ, start_response)
    

class BaseController(WSGIController): pass


# Include the '_' function in the public names
__all__ = [__name for __name in locals().keys() if not __name.startswith('_')]
__all__.append('_')

