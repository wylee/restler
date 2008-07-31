import logging

from pylons import request
from pylons import tmpl_context as c
from pylons.controllers import WSGIController
from pylons.controllers.util import abort, redirect_to
from pylons.decorators import jsonify
from pylons.templating import render_mako as render

import mako


log = logging.getLogger(__name__)

TemplateNotFoundExceptions = (mako.exceptions.TopLevelLookupException,)


def RestController(the_model):
    """Return a ``RestController`` that's aware of a particular model."""
    class RestController(_RestController):
        model = the_model
    return RestController


class _RestController(WSGIController):
    model = None

    def __call__(self, environ, start_response):
        try:
            return super(_RestController, self).__call__(
                environ, start_response)
        finally:
            self.model.clear_session()

    def __before__(self, *args, **kwargs):
        route = request.environ['routes.route']
        route_info = request.environ['pylons.routes_dict']

        log.debug(route_info)

        c.path = request.environ['PATH_INFO']
        log.debug('Path: %s' % c.path)

        member_name = route.member_name
        log.debug('Member name: %s' % member_name)

        entity_name = member_name.replace('_', ' ').title().replace(' ', '')
        log.debug('Entity name: %s' % entity_name)

        c.format = kwargs.get('format', 'html')
        log.debug('Output format: %s' % c.format)

        c.controller = route_info['controller']
        c.action = route_info['action']

        c.Entity = getattr(self.model, entity_name)

        c.member_name = c.Entity.member_name
        c.member_title = c.Entity.member_title

        c.collection_name = c.Entity.collection_name
        c.collection_title = c.Entity.collection_title

    def index(self):
        self._set_collection()
        return self._render()

    def show(self, id):
        self._set_member(id)
        return self._render()

    def new(self):
        self._set_member()
        return self._render()

    def edit(self, id):
        self._set_member(id)
        return self._render()

    def create(self):
        self._set_member()
        self._update_member_with_params()
        self.model.Session.add(c.member)
        self.model.Session.flush()
        self._redirect_to_member()

    def update(self, id):
        self._set_member(id)
        self._update_member_with_params()
        self.model.Session.flush()
        self._redirect_to_member()

    def delete(self, id):
        self._set_member(id)
        self.model.Session.delete(c.member)
        self.model.Session.flush()
        self._redirect_to_collection()

    def _set_member(self, id=None):
        if id is None:
            member = c.Entity()
        else:
            member = self._get_entity_or_404(id)
        c.member = member
        setattr(c, c.member_name, member)

    def _set_collection(self):
        collection = self.model.Session.query(c.Entity).all()
        c.collection = collection
        setattr(c, c.collection_name, c.collection)

    def _get_entity_or_404(self, id):
        entity = self.model.Session.query(c.Entity).get(id)
        if entity is None and hasattr(c.Entity, 'slug'):
            entity = self.model.Session.query(c.Entity).filter_by(slug=id).one()
        if entity is None:
            abort(404, 'Member with ID "%s" not found' % id)
        return entity

    def _update_member_with_params(self):
        params = request.params
        for name in params:
            setattr(c.member, name, params[name])

    def _redirect_to_member(self):
        redirect_to('admin_%s' % c.member_name, id=c.member.id)

    def _redirect_to_collection(self):
        redirect_to('admin_%s' % c.collection_name)

    def _render(self, *args, **kwargs):
        format = c.format or 'html'
        render = getattr(self, '_render_%s' % format, self._render_html)
        return render(*args, **kwargs)

    def _render_html(
        self, controller=None, action=None, format=None, namespace=None):
        template = '/%%s/%s.%s' % (action or c.action, format or c.format)
        try:
            template_name = template % (controller or c.controller)
            return render(template_name)
        except TemplateNotFoundExceptions:
            if namespace is not None:
                template = '%s/%s' % (namespace, template)
            template_name = template % 'default'
            return render(template_name)
        finally:
            log.debug('(_render) template: %s' % template_name)

    def _render_json(self, block=None):
        if c.collection is not None:
            obj = [member.to_builtin() for member in self.collection]
        elif c.member is not None:
            obj = c.member.to_builtin()
        else:
            obj = None
        return self._render_obj_as_json(obj, block)

    @jsonify
    def _render_object_as_json(self, obj, block=None):
        """Render an object in JSON format with content type of text/json.

        ``obj`` must be JSONifiable by the simplejson module.

        The final output of this method is returned by the ``jsonify``
        decorator, which creates a proper JSON response with the correct
        content type.

        """
        if block is not None:
            obj = block(obj)
        return obj
