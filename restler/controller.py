import logging

from paste.deploy.converters import asbool, aslist

from pylons import request, response, url
from pylons import tmpl_context as c
from pylons.controllers import WSGIController
from pylons.controllers.util import abort, redirect
from pylons.decorators import jsonify
from pylons.templating import render_mako as render

from sqlalchemy.orm import class_mapper

import mako.exceptions

try:
    import json
except ImportError:
    import simplejson as json


log = logging.getLogger(__name__)

TemplateNotFoundExceptions = (mako.exceptions.TopLevelLookupException,)


class NoDefaultValue(object):

    def __new__(self, *args, **kwargs):
        raise NotImplementedError('This class may not be instantiated.')


class Controller(WSGIController):

    entity = None
    """Entity class assocated with this controller."""

    base_filter_params = dict(
        where_clause=NoDefaultValue,  # Any valid SQL where clause fragment
        distinct=False,
        offset=None,
        start=None,
        limit=None,
        order_by=None,
    )

    filter_params = {}
    """Request param names with defaults, for filtering collections."""

    filters = []
    """SQLAlchemy filters--anything that can be an arg to `query().filter`.

    These filters are *not* request-specific--they are applied on *every*
    request.

    """

    default_format = 'json'

    def __call__(self, environ, start_response):
        try:
            return super(Controller, self).__call__(environ, start_response)
        finally:
            log.debug('Clearing database session...')
            self.db_session.remove()

    def __before__(self, *args, **kwargs):
        self.db_session.get_bind(class_mapper(self.entity))
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

    def _get_db_session(self):
        """Database session factory.

        The default implementation here assumes that subclasses have a public
        :meth:`get_db_session` method. The session returned from that method
        is cached per :class:`Controller` instance.

        """
        try:
            self._db_session
        except AttributeError:
            self._db_session = self.get_db_session()
        return self._db_session
    def _set_db_session(self, db_session):
        self._db_session = db_session
    db_session = property(_get_db_session, _set_db_session)

    def get_db_session(self):
        raise NotImplementedError

    @property
    def collection_path(self):
        """Path to collection, including application path prefix."""
        try:
            self._collection_path
        except AttributeError:
            self._collection_path = '/'.join((
                request.path.rsplit(self.collection_name, 1)[0].rstrip('/'),
                self.collection_name))
        return self._collection_path

    def get_member_path(self, member):
        """Path to member, including application path prefix."""
        id = getattr(member, 'id_str', None)
        return '{0}/{1}'.format(self.collection_path, id)

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

    def create(self):
        self.set_member()
        self._update_member_with_params()
        self.db_session.add(self.member)
        self.db_session.flush()
        self.db_session.commit()
        self._redirect_to_member()

    def update(self, id):
        self.set_member(id)
        self._update_member_with_params()
        self.db_session.flush()
        self.db_session.commit()
        self._redirect_to_member()

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

    def set_collection(self, q=None, extra_filters=None):
        q = q if q is not None else self.db_session.query(self.entity)

        # Apply "global" (i.e., every request) filters
        filters = (self.filters or []) + (extra_filters or [])
        for f in filters:
            q = q.filter(f)

        # Apply per-request filters
        filters = self._set_filters_from_params(self.base_filter_params)
        filters.update(self._set_filters_from_params(self.filter_params))

        distinct = asbool(filters.pop('distinct', False))
        offset = filters.pop('offset', filters.pop('start', None))
        limit = filters.pop('limit', None)
        order_by = filters.pop('order_by', None)

        where_clause = filters.pop('where_clause', NoDefaultValue)
        if where_clause is not NoDefaultValue:
            q = q.filter(where_clause)

        for k, v in filters.items():
            v = self.convert_param(k, v)
            filter_method = getattr(self.entity, 'filter_by_%s' % k, None)
            if filter_method is not None:
                q = filter_method(q, v)
            else:
                q = q.filter_by(**{k: v})

        if distinct:
            q = q.distinct()
        if order_by is not None:
            q = q.order_by(*aslist(order_by, ','))
        if offset is not None:
            q = q.offset(int(offset))
        if limit is not None:
            q = q.limit(int(limit))

        self.collection = q.all() or abort(404)

    def _set_filters_from_params(self, filter_params):
        filters = {}
        params = request.params
        for name in filter_params:
            if name in params:
                # Use param value unless it's blank. XXX: Don't strip?
                val = params.get(name)
                if val.strip() == '':
                    val = filter_params[name]
            else:
                val = filter_params[name]
            if val is not NoDefaultValue:
                if callable(val):
                    val = val()
                filters[name] = val
        return filters

    def get_entity_or_404(self, id):
        id = self.entity.str_to_id(id)
        entity = self.db_session.query(self.entity).get(id) or abort(404)
        return entity

    def _update_member_with_params(self):
        params = request.params
        for name in params:
            val = self.convert_param(name, params[name])
            setattr(self.member, name, val)

    def convert_param(self, name, val):
        """Convert param value (string) to Python value."""
        return self.entity.convert_param(name, val)

    def _do_redirect(self, url_args, redirect_args=None):
        _url_args = dict(
            controller=self.controller,
            format=self.format,
        )
        _url_args.update(url_args)
        redirect_url = url(**_url_args)
        if request.is_xhr:
            # X-Restler-Client-Request-URL is the URL used by the client to
            # make requests to the Web service that is utilizing Restler.
            # This is only relevant when using AJAX due to same-origin
            # restrictions.
            base_url = request.headers.get('X-Restler-Client-Request-URL', None)
            if base_url is not None:
                redirect_url = base_url.rstrip('/') + redirect_url
        _redirect_args = dict(code=303)
        _redirect_args.update(redirect_args or {})
        redirect(redirect_url, **_redirect_args)

    def _redirect_to_member(self, member=None, relay_params=None, params=None):
        """Redirect to a specific ``member``, defaulting to `self.member`.

        ``relay_params`` List of params to relay from original request. If
        a param isn't in the original request, it's ignored and not relayed
        to the redirect.

        ``params`` Dict of additional params; will override ``relay_params``.

        """
        member = self.member if member is None else member
        url_args = {}
        if relay_params:
            for key in relay_params:
                if key in request.params:
                    url_args[key] = request.params[key]
        if params:
            for key in params:
                url_args[key] = params[key]
        url_args.update(action='show', id=member.id)
        self._do_redirect(url_args)

    def _redirect_to_collection(self):
        self._do_redirect(dict(action='index'))

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
        obj = self._get_json_object(wrap=self.wrap, block=block)
        return self._render_object_as_json(obj)

    @jsonify
    def _render_object_as_json(self, obj):
        """Render an object in JSON format with correct content type.

        ``obj`` must be JSONifiable by the (simple)json module.

        The final output of this method is returned by the Pylons ``jsonify``
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
        if self.collection is not None:
            log.debug('Rendering collection')
            items = self.collection
        elif self.member is not None:
            log.debug('Rendering member')
            items = [self.member]
        else:
            log.debug('Neither collection nor member was set.')
            items = None
            obj = None
            result_count = 0

        if items is not None:
            obj = self.entity.to_simple_collection(items, self.fields)
            for member, simple_member in zip(items, obj):
                simple_member['__path__'] = self.get_member_path(member)
            result_count = len(obj)

        # Wrap ``obj`` (usually)
        if wrap:
            obj = dict(
                response=dict(
                    results=obj,
                    result_count=result_count,
                    request=dict(
                        method=request.method,
                        full_url=request.url,  # URL with query string
                        host_url=request.host_url,  # URL of host (no path or query)
                        app_prefix=request.script_name,  # Path to app
                        path=request.path,  # Path *including* app prefix
                        collection_path=self.collection_path,  # *Includes* app prefix
                        params=(request.params.items() or None),
                        query_string=(request.query_string or None),
                    ),
                )
            )
        # Further modify ``obj`` if ``block`` given
        if block is not None:
            obj = block(obj)
        return obj

    @property
    def fields(self):
        """Return list of fields to include in response.

        The `fields` request parameter should be a JSON `list`. This property
        merely decodes the parameter from JSON into a Python object and
        returns it. See :class:`restler.entity.Entity` for documentation on
        the expected form and contents of the list.

        Example (URL-encoded)::

            /path?fields=["*","%2Bmy_attr"]

            Decoded from JSON: `['*', '+my_attr']`

        """
        try:
            self._fields
        except AttributeError:
            fields = request.params.get('fields', None)
            if fields is not None:
                fields = json.loads(fields)
            self._fields = fields
        return self._fields

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
        attr = getattr(self.__class__, name, None)
        if isinstance(attr, property) and attr.fset is not None:
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
