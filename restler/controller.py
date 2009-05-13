import logging

from paste.deploy.converters import asbool

from pylons import request, response
from pylons import tmpl_context as c
from pylons.controllers import WSGIController
from pylons.controllers.util import abort, redirect_to
from pylons.decorators import jsonify
from pylons.templating import render_mako as render

from sqlalchemy.orm.exc import NoResultFound

import mako

import simplejson as json

from restler.decorators import privileged
"""Set `privileged` BEFORE importing this module, if needed."""


log = logging.getLogger(__name__)

TemplateNotFoundExceptions = (mako.exceptions.TopLevelLookupException,)


class Controller(WSGIController):

    entity = None
    """Entity class assocated with this controller."""

    filter_params = {}
    """Request param names with defaults, for filtering collections."""

    filters = []
    """SQLAlchemy filters--anything that could be an arg to `q.filter`."""

    default_format = 'json'

    def __call__(self, environ, start_response):
        try:
            return super(Controller, self).__call__(environ, start_response)
        finally:
            log.debug('Clearing database session...')
            self.db_session.remove()

    def __before__(self, *args, **kwargs):
        route_info = request.environ['pylons.routes_dict']
        self.controller = route_info['controller']
        self.action = route_info['action']
        self.member_name = self.entity.member_name
        self.member_title = self.entity.member_title
        self.collection_name = self.entity.collection_name
        self.collection_title = self.entity.collection_title
        self.format = kwargs.get('format',
            request.params.get('format', self.default_format))
        self._init_properties()
        log.debug('Action: %s' % self.action)

    @property
    def db_session(self):
        """Database session factory.

        The default implementation here assumes that an :attr:`entity` has a
        :meth:`get_session` method. The session returned from that method is
        cached per :class:`Controller` instance.

        """
        try:
            self._db_session
        except AttributeError:
            self._db_session = self.entity.get_session()
        return self._db_session

    def index(self):
        self.set_collection()
        return self._render()

    def show(self, id):
        self.set_member(id)
        return self._render()

    def new(self):
        self.set_member()
        return self._render()

    def edit(self, id):
        self.set_member(id)
        return self._render()

    @privileged
    def create(self):
        self.set_member()
        self._update_member_with_params()
        self.db_session.add(self.member)
        self.db_session.flush()
        self.db_session.commit()
        self._redirect_to_member()

    @privileged
    def update(self, id):
        self.set_member(id)
        self._update_member_with_params()
        self.db_session.flush()
        self.db_session.commit()
        self._redirect_to_member()

    @privileged
    def delete(self, id):
        self.set_member(id)
        self.db_session.delete(self.member)
        self.db_session.flush()
        self.db_session.commit()
        self._redirect_to_collection()

    def set_member(self, id=None):
        if id is None:
            member = self.entity()
        else:
            member = self.get_entity_or_404(id)
        self.member = member

    # TODO: Allow pagination for collection methods. If pagination params
    # aren't set then we'd just fall through to returning the entire
    # collection OR if the collection is huge, we might use defaults.

    def set_collection(self):
        params = request.params
        kwargs = {}
        if self.filters:
            kwargs['filters'] = self.filters
        for name in self.filter_params:
            val = params.get(name, '').strip()
            if val == '':
                val = self.filter_params[name]
            kwargs[name] = val
        self.collection = self.entity.all(**kwargs) or abort(404)

    def get_entity_or_404(self, id):
        # TODO: Allow get by alt pk
        entity = self.db_session.query(self.entity).get(id) or abort(404)
        return entity

    def _update_member_with_params(self):
        params = request.params
        for name in params:
            val = self._convert_param_for_update(name, params[name])
            setattr(self.member, name, val)

    def _convert_param_for_update(self, name, val):
        return val

    def _redirect_to_member(self):
        redirect_to(self.member_name, id=self.member.id)

    def _redirect_to_collection(self):
        redirect_to(self.collection_name)

    def _render(self, *args, **kwargs):
        format = kwargs.get('format', self.format)
        log.debug('Output format: %s' % format)
        kwargs['format'] = format
        render = getattr(self, '_render_%s' % format, self._render_template)
        log.debug('Render method: %s *%s **%s' % (render.__name__, args, kwargs))
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

    def _render_json(self, block=None, **kwargs):
        """Render a JSON response from simplified ``member``s."""
        obj = self._get_json_object(block=block)
        return self._render_object_as_json(obj)

    @jsonify
    def _render_object_as_json(self, obj):
        """Render an object in JSON format with content type of text/json.

        ``obj`` must be JSONifiable by the (simple)json module.

        The final output of this method is returned by the ``jsonify``
        decorator, which creates a proper JSON response with the correct
        content type.

        """
        return obj

    def _get_json_object(self, wrap=True, block=None):
        """Get JSON object for current request.

        ``wrap``
             If set, the output will be wrapped in a dict.

        ``block``
            Can be passed to modify or wrap the object before JSONifying it.
            In this case the wrapping discussed above under ``obj`` won't
            happen.

        """
        fields = self.fields
        if self.collection is not None:
            log.debug('Rendering collection')
            if fields:
                simplifier = self.entity.simplify_object
                obj = []
                for member in self.collection:
                    result = {}
                    for name, as_name in fields:
                        result[as_name] = simplifier(getattr(member, name))
                    obj.append(result)
            else:
                obj = self.entity.to_simple_collection(self.collection)
            result_count = len(obj)
        elif self.member is not None:
            log.debug('Rendering member')
            if fields:
                simplifier = self.entity.simplify_object
                obj = {}
                for name, as_name in fields:
                    obj[as_name] = simplifier(getattr(self.member, name))
            else:
                obj = [self.member.to_simple_object()]
            result_count = 1
        else:
            log.debug('Neither collection nor member was set.')
            obj = None
            result_count = 0
        # Wrap ``obj`` (usually)
        if self.wrap:
            total_count = self.db_session.query(self.entity).count()
            obj = dict(
                response=dict(
                    results=obj,
                    result_count=result_count,
                    total_count=total_count
                )
            )
        # Further modify ``obj`` if ``block`` given
        if block is not None:
            obj = block(obj)
        return obj

    @property
    def fields(self):
        """Fields to include in the response."""
        fields = request.params.get('fields', None)
        if fields:
            fields = json.loads(fields)
            if isinstance(fields, list):
                fields = dict((name, name) for name in fields)
            fields = fields.items()
        return fields

    def _get_wrap(self):
        try:
            self._wrap
        except AttributeError:
            self._set_wrap()
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
        if value is None:
            wrap = request.params.get('wrap', 'true')
            self._wrap = asbool(wrap)
        else:
            self._wrap = value
        c.wrap = self._wrap
    wrap = property(_get_wrap, _set_wrap)

    def __setattr__(self, name, value):
        """Set attribute on both ``self`` and ``c``."""
        if isinstance(getattr(self.__class__, name, None), property):
            # I.e., just call the property's _set method
            super(Controller, self).__setattr__(name, value)
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
