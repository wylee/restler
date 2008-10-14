import logging

from pylons import request, response
from pylons import tmpl_context as c
from pylons.controllers import WSGIController
from pylons.controllers.util import abort, redirect_to
from pylons.decorators import jsonify
from pylons.templating import render_mako as render

from sqlalchemy.orm.exc import NoResultFound

import mako


log = logging.getLogger(__name__)

TemplateNotFoundExceptions = (mako.exceptions.TopLevelLookupException,)


def RestController(the_model):
    """Return a ``RestController`` class that's aware of a particular model."""
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
            log.debug('Removing Session...')
            self.model.Session.remove()

    def __before__(self, *args, **kwargs):
        route = request.environ['routes.route']
        route_info = request.environ['pylons.routes_dict']

        log.debug(route_info)

        self.path = request.environ['PATH_INFO']
        log.debug('Path: %s' % self.path)

        member_name = route.member_name
        log.debug('Member name: %s' % member_name)

        entity_name = member_name.replace('_', ' ').title().replace(' ', '')
        log.debug('Entity name: %s' % entity_name)

        self.format = request.params.get('format', kwargs.get('format', 'html'))
        log.debug('Output format: %s' % self.format)

        self.controller = route_info['controller']
        self.action = route_info['action']

        self.Entity = getattr(self.model, entity_name)

        self.member_name = self.Entity.member_name
        self.member_title = self.Entity.member_title

        self.collection_name = self.Entity.collection_name
        self.collection_title = self.Entity.collection_title

        self.member = None
        self.collection = None

        self._set_wrap()

        self._init_properties()

    def index(self):
        params = request.params
        filters = params.keys()
        not_filters = ['wrap', 'format']
        filters = [p for p in params if p not in not_filters]
        if filters:
            self.set_collection_by_filters(params)
        else:
            self.set_collection_by_ids()
        return self._render()

    def show(self, id):
        self.set_member_by_id(id)
        return self._render()

    def new(self):
        self.set_member_by_id()
        return self._render()

    def edit(self, id):
        self.set_member_by_id(id)
        return self._render()

    def create(self):
        self.set_member_by_id()
        self._update_member_with_params()
        self.model.Session.add(self.member)
        self.model.Session.flush()
        self._redirect_to_member()

    def update(self, id):
        self.set_member_by_id(id)
        self._update_member_with_params()
        self.model.Session.flush()
        self._redirect_to_member()

    def delete(self, id):
        self.set_member_by_id(id)
        self.model.Session.delete(self.member)
        self.model.Session.flush()
        self._redirect_to_collection()

    def set_member_by_id(self, id=None):
        if id is None:
            member = self.Entity()
        else:
            member = self.get_entity_or_404(id)
        self.member = member

    _set_member = set_member_by_id

    # TODO: Allow pagination for collection methods. If pagination params
    # aren't set then we'd just fall through to returning the entire
    # collection.

    def set_collection_by_ids(self, ids=None):
        q = self.model.Session.query(self.Entity)
        if ids is not None:
            q = q.filter(self.Entity.id.in_(ids))
        self.collection = q.all()

    _set_collection = set_collection_by_ids

    def set_collection_by_filters(self, filters):
        q = self.model.Session.query(self.Entity)
        for col in filters:
            val = filters[col]
            q = q.filter_by(**{col: val})
        self.collection = q.all()

    def get_entity_or_404(self, id):
        # Try to find by primary key
        q = self.model.Session.query(self.Entity)
        try:
            int(id)
        except ValueError:
            entity = None
        else:
            entity = q.get(id)
        # If that fails, try to find by slug
        if entity is None and hasattr(self.Entity, 'slug'):
            try:
                entity = q.filter_by(slug=id).one()
            except NoResultFound:
                abort(404, 'Member with ID or slug "%s" was not found.' % id)
        return entity

    _get_entity_or_404 = get_entity_or_404

    def _update_member_with_params(self):
        params = request.params
        for name in params:
            setattr(self.member, name, params[name])

    def _redirect_to_member(self):
        redirect_to(self.member_name, id=self.member.id)

    def _redirect_to_collection(self):
        redirect_to(self.collection_name)

    def _render(self, *args, **kwargs):
        format = kwargs.get('format', self.format or 'html')
        kwargs['format'] = format
        kwargs['action'] = kwargs.get('action', self.action)
        render = getattr(self, '_render_%s' % format, self._render_template)
        log.debug('Render method: %s' % render.__name__)
        response.status = kwargs.pop('code', 200)
        return render(*args, **kwargs)

    def _render_template(
        self, controller=None, action=None, format=None, namespace=None):
        """By default, render template /{controller}/{action}.{format}.

        This is the default rendering method, used when a specific
        ``render_<format>`` method doesn't exist. Templates can be any
        text-based template--HTML, text, XML, etc.

        Typically, args are set in the environment (on ``c``), except
        ``namespace``. Args passed explicitly will override args set in the
        env. If ``namespace`` is given, the template rendered will be
        /namespace/{controller}/{action}.{format}.

        """
        template = '/%%s/%s.%s' % (action or self.action, format or self.format)
        try:
            template_name = template % (controller or self.controller)
            return render(template_name)
        except TemplateNotFoundExceptions:
            if namespace is not None:
                template = '%s/%s' % (namespace, template)
            template_name = template % 'default'
            return render(template_name)
        finally:
            log.debug('(_render) template: %s' % template_name)

    def _render_json(self, action=None, block=None, **kwargs):
        """Render a JSON response from simplified ``member``s."""
        obj = self._get_json_object(action=action, block=block)
        return self._render_object_as_json(obj)

    @jsonify
    def _render_object_as_json(self, obj):
        """Render an object in JSON format with content type of text/json.

        ``obj`` must be JSONifiable by the simplejson module.

        The final output of this method is returned by the ``jsonify``
        decorator, which creates a proper JSON response with the correct
        content type.

        """
        return obj

    def _get_json_object(self, action=None, wrap=True, block=None):
        """Get JSON object for current request.

        ``wrap``
             If set, the output will be wrapped as {result: obj} to avoid JSON
             Array exploits.

        ``block``
            Can be passed to modify or wrap the object before JSONifying it.
            In this case the wrapping discussed above under ``obj`` won't
            happen.

        """
        if self.collection is not None:
            obj = [member.to_simple_object() for member in self.collection]
        elif self.member is not None:
            obj = self.member.to_simple_object()
        else:
            log.debug('Neither collection nor member was set.')
            obj = None
        if block is not None:
            obj = block(obj)
        if wrap:
            obj = dict(result=obj)
        return obj

    def _get_wrap(self):
        return self._wrap
    def _set_wrap(self, value=None):
        """Set whether to wrap a template in its parent template.

        If ``value`` is given, use that value. If ``wrap`` is set in
        ``request.params``, convert its value to ``bool`` and use that
        value. Otherwise, set ``self.wrap`` to True.

        ``value``
            ``bool`` indicating whether or not a template should be
            wrapped in its inherited templates. ``wrap`` gets passed along
            to the template, which can decide to do whatever it wants with
            it.

        """
        if value is not None:
            self._wrap = value
        else:
            wrap = request.params.get('wrap', 'true').strip().lower()
            if wrap in ('0', 'n', 'no', 'false', 'nil'):
                self._wrap = False
            else:
                self._wrap = True
        c.wrap = self._wrap
    wrap = property(_get_wrap, _set_wrap)

    def __setattr__(self, name, value):
        """Set attribute on both ``self`` and ``c``."""
        if isinstance(getattr(self.__class__, name, None), property):
            # I.e., just call the property's _set method
            super(_RestController, self).__setattr__(name, value)
        else:
            self._set_property([name], value)

    def _set_property(self, names, value):
        """Set attributes on both ``self`` and ``c``."""
        for name in names:
            self.__dict__[name] = value
            # Don't put "private" names in the template context
            if not name.startswith('_'):
                setattr(c, name, value)

    def _p_get_collection(self):
        return self.__dict__.get('collection', None)
    def _p_set_collection(self, collection):
        self._set_property(
            ['collection', self.collection_name], collection)
    collection = property(_p_get_collection, _p_set_collection)

    def _p_get_member(self):
        return self.__dict__.get('member', None)
    def _p_set_member(self, member):
        self._set_property(['member', self.member_name], member)
    member = property(_p_get_member, _p_set_member)

    def _init_properties(self):
        cls = self.__class__
        setattr(cls, self.collection_name, cls.collection)
        setattr(cls, self.member_name, cls.member)
