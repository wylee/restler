from pylons import Response, c, request
from pylons.controllers import WSGIController
from pylons.templating import render, render_response
from pylons.helpers import abort, redirect_to
from pylons.util import class_name_from_module_name
from pylons.database import create_engine

import sqlalchemy

import elixir
from elixir import objectstore

import simplejson

__all__ = ['BaseController', 'init_model', 'engine', 'metadata',
           'objectstore', 'session_context']


engine, metadata, session_context = None, None, None
model_initialized = False


def init_model(the_model):
    global model, engine, metadata, session_context, model_initialized

    model = the_model
    """Module containing Elixir ``Entity`` classes."""

    metadata = getattr(model, 'metadata', elixir.metadata)
    """SQLAlchemy metadata. Prefer metadata defined in ``model``."""

    try:
        engine = getattr(model, 'engine', create_engine())
        """SQLAlchemy database engine. Prefer engine defined in ``model``."""
    except TypeError:
        # This happens when ``model`` doesn't define ``engine`` and
        # ``create_engine`` gets called--the Pylons ``create_engine`` only
        # works when the site is running because it magically gets the DB
        # config from INI file the site is running under.
        import sys
        sys.stderr.write('WARNING: Database engine was not defined in '
                         '``model`` and could not be created.\n')
    else:
        if not metadata.is_bound():
            metadata.connect(engine)

    session_context = getattr(model, 'session_context', objectstore.context)

    model_initialized = True


class BaseController(WSGIController):
    """Base class for RESTful controllers."""

    def __call__(self, environ, start_response):
        return super(BaseController, self).__call__(environ, start_response)

    def __init__(self):
        """Initialize RESTful Controller.

        It is assumed that the controller file is named after the resource's
        collection name and that there is a corresponding top level template
        directory. For example, for a Hat resource, the controller file will
        be named hats.py and there will be a template directory at
        /templates/hats.

        """
        if not model_initialized:
            raise ValueError("""
``restler.init_model`` must be called with the module that contains (or
imports) your Elixir ``Entity`` classes before the ``restler.BaseController``
class can be used:

    import some_module as model
    import restler
    restler.init_model(model)
""")

        del session_context.current

        route = request.environ['routes.route']
        route_info = request.environ['pylons.routes_dict']

        self.controller = route_info['controller']
        self.action = route_info['action']

        self.format = request.params.get('format',
                                         route_info.get('format', None))
        self.template = request.params.get('template', None)
        self._set_wrap()

        self.collection_name = (getattr(self, 'collection_name', None) or
                                route.collection_name)
        self.member_name = (getattr(self, 'member_name', None) or
                            route.member_name)

        # Import entity class for resource
        self.entity_name = class_name_from_module_name(self.member_name)
        self.Entity = getattr(model, self.entity_name)

        # Do setup for parent resource, if this resource is nested
        self.parent_resource = route.parent_resource
        if self.parent_resource is not None:
            self.is_nested = True

            name = (getattr(self, 'parent_member_name', None) or
                    self.parent_resource['member_name'])
            self.parent_member_name = name

            self.parent_id_name = '%s_id' % name
            self.parent_id = route_info.get(self.parent_id_name)

            name = (getattr(self, 'parent_collection_name', None) or
                    self.parent_resource['collection_name'])
            self.parent_collection_name = name

            name = (getattr(self, 'grandparent_member_name', None) or
                    self.parent_resource.get('parent_member_name', None))
            self.grandparent_member_name = name

            # Import entity class for parent resource
            f = class_name_from_module_name
            self.parent_entity_name = f(self.parent_member_name)
            self.ParentEntity = getattr(model, self.parent_entity_name)

            self._set_parent_by_id(self.parent_id)
        else:
            self.is_nested = False

        # Create aliases for the generically named properties (``member``,
        # ``parent``, etc), using the resource and its parent's actual names.
        # For example, if the resource's member name is "cat", the property
        # ``cat`` will be created. It will correspond to the generically
        # named property ``member``.
        cls = self.__class__
        setattr(cls, self.collection_name, cls.collection)
        setattr(cls, self.member_name, cls.member)
        if self.is_nested:
            setattr(cls, self.parent_id_name, cls.parent_id)
            setattr(cls, self.parent_member_name, cls.parent)

    def index(self):
        """GET /

        Show all (or subset of) items in collection.

        """
        self._set_collection_by_id()
        return self._render_response()

    def new(self):
        """GET /resource/new

        Show a form for creating a new item. The form should POST to
        /resource/create.

        Example using WebHelpers::

            >>> import webhelpers as h
            >>> h.form(h.url_for('sites'))
            '<form action="sites" method="POST">'
            >>> h.text_field('whatever')
            '<input id="whatever" name="whatever" type="text" />'
            >>> h.end_form()
            '</form>'

        """
        self.member = self.Entity()
        return self._render_response()

    def show(self, id=None):
        """GET /resource/id

        Show existing item that has ID ``id``.

        """
        self._set_member_by_id(id)
        return self._render_response()

    def edit(self, id=None):
        """GET /resource/id;edit

        Show a form for editing an existing item that has ID ``id``. The form
        should PUT to /resource/update (but since is not well-supported, we
        use POST with a hidden input field to indicate it's really a PUT).

        Example using WebHelpers::

            >>> import webhelpers as h
            >>> h.form(h.url_for('sites/13'), method='PUT')
            '<form action="sites/13" method="POST"><input id="_method" name="_method" type="hidden" value="PUT" />'
            >>> h.text_field('whatever')
            '<input id="whatever" name="whatever" type="text" />'
            >>> h.end_form()
            '</form>'

        """
        self._set_member_by_id(id)
        return self._render_response()

    def create(self):
        """POST /resource

        Create a new member using POST data.

        """
        self.member = self.Entity()
        self._update_member_with_params()
        self._redirect_to_member()

    def update(self, id=None):
        """PUT /resource/id

        Update with PUT data an existing item that has ID ``id`` .

        """
        self._set_member_by_id(id)
        self._update_member_with_params()
        self._redirect_to_member()

    def _update_member_with_params(self):
        params = request.params
        for name in params:
            setattr(self.member, name, params[name])
        if self.is_nested:
            setattr(self.member, self.parent_id_name, self.parent_id)
        self.member.flush()
        self.member.refresh()

    def _redirect_to_member(self):
        args = {'id': self.member.id, 'action': 'show',
                'format': self.format}
        if self.is_nested:
            args[self.parent_id_name] = self.parent_id
        redirect_to(**args)

    def delete(self, id=None):
        """DELETE /resource/id

        Delete the existing item that has ID ``id``. Redirect to resource
        ``index`` after deletion.

        """
        self._set_member_by_id(id)
        self.member.delete()
        self.member.flush()
        self._redirect_to_collection()

    def _redirect_to_collection(self):
        args = {'action': 'index', 'format': self.format}
        if self.is_nested:
            args[self.parent_id_name] = self.parent_id
        redirect_to(**args)

    def __setattr__(self, name, value):
        """Set attribute on both ``c`` and ``self``."""
        if isinstance(getattr(self.__class__, name, None), property):
            # I.e., just call the property's _set method
            super(BaseController, self).__setattr__(name, value)
        else:
            self._set_property([name], value)

    def _set_property(self, names, value):
        for name in names:
            self.__dict__[name] = value
            # Don't put "private" names in the template context
            if not name.startswith('_'):
                setattr(c, name, value)

    def _get_parent(self):
        return self.__dict__.get('parent', None)
    def _set_parent(self, parent):
        self._set_property(('parent', self.parent_member_name), parent)
    parent = property(_get_parent, _set_parent)

    def _get_parent_id(self):
        return self.__dict__.get('parent_id', None)
    def _set_parent_id(self, parent_id):
        self._set_property(('parent_id', self.parent_id_name), parent_id)
    parent_id = property(_get_parent_id, _set_parent_id)

    def _get_collection(self):
        return self.__dict__.get('collection', None)
    def _set_collection(self, collection):
        self._set_property(('collection', self.collection_name), collection)
    collection = property(_get_collection, _set_collection)

    def _get_member(self):
        return self.__dict__.get('member', None)
    def _set_member(self, member):
        self._set_property(('member', self.member_name), member)
    member = property(_get_member, _set_member)

    def _set_parent_by_id(self, parent_id):
        self.parent = self._get_entity_or_404(self.ParentEntity, parent_id)

    def _set_member_by_id(self, id):
        args = {}
        if self.is_nested:
            args[self.parent_id_name] = self.parent.id
        self.member = self._get_entity_or_404(self.Entity, id, **args)

    def _get_entity_or_404(self, Entity, id, **kwargs):
        """Get entity with ID ``id``

        ``Entity``
            The entity model class to select from

        ``id``
            The entity's ID

        ``kwargs``
            Other column name/value pairs used to narrow the select. This is
            used internally by ``_set_member_by_id`` to filter the select if
            there's a parent resource (e.g., kwargs = {'parent_id': 123}).

        """
        entity = None
        if 'slug' in Entity.c:
            entity = Entity.get_by(slug=str(id), **kwargs)
        if entity is None:
            try:
                entity = Entity.get_by(id=id, **kwargs)
            except sqlalchemy.exceptions.SQLError:
                # Avoids error with mismatched primary keep type
                # TODO: There's probably a better way to do this
                pass
        if entity is None:
            abort(404, 'Member with ID "%s" not found' % id)
        return entity

    def _set_collection_by_id(self, parent_id=None, page=0, num_items=10):
        args = {}
        if self.is_nested:
            args[self.parent_id_name] = self.parent.id
        collection = self.Entity.select_by(**args)
        if not collection:
            abort(404, 'No collection members found')
        else:
            self.collection = collection

    def _render_response(self, format=None, template=None, wrap=None,
                         **response_args):
        """Render a response for those actions that return content.

        ``format``
            An alternative format for the response content; by default,
            ``format`` from ``request.params`` is used

        ``template``
            An alternative template; by default, a template named after the
            action is used

        ``wrap``
            A ``bool`` indicating whether or not to "wrap" a template in its
            inherited templates(s). This is an alternative wrap setting; by
            default, the wrap setting comes from ``request.params``.

        ``response_args``
            The remaining keyword args will be passed to the ``Response``
            costructor

        return ``Response``

        """
        # Dynamically determine the content method
        format = (format or self.format or 'html').strip().lower()
        _get_content = getattr(self, '_get_%s_content' % (format))

        # _get_<format>_content methods need to add file extension (if needed)
        tmpl = (template or self.template or self.action)
        self._template_path = '/%s/%s' % (self.collection_name, tmpl)

        if wrap is not None:
            self.wrap = wrap

        content, mimetype = _get_content()
        response_args.update(dict(content=content, mimetype=mimetype))
        response = Response(**response_args)
        return response

    def _get_html_content(self):
        """Get HTML content and mimetype."""
        html = render('%s.html' % self._template_path)
        return html, 'text/html'

    def _get_text_content(self):
        """Get plain text content and mimetype."""
        text = render('%s.txt' % self._template_path)
        return text, 'text/plain'
    _get_txt_content = _get_text_content

    def _get_xml_content(self):
        """Get XML content."""
        html = render('%s.xml' % self._template_path)
        return html, 'text/xml'

    def _get_json_content(self, block=None):
        """Get a JSON string and mimetype "text/javascript".

        Assumes members have a ``__simplify__`` method that returns an object
        that can be JSONified by the ``simplejson module``. That object is
        JSONified and returned unless the ``block`` arg is supplied.

        ``block``
            This method creates the simplest possible object to be JSONified
            (``obj``) by calling ``__simplify__`` on a member or members. If a
            function is passed via ``block``, that function will be called
            with ``obj``, and ``obj`` can be modified there before being
            JSONified here.

        """
        if self.collection is not None:
            obj = [m.__simplify__() for m in self.collection]
        elif self.member is not None:
            obj = self.member.__simplify__()
        else:
            obj = None
        if block is not None:
            obj = block(obj)
        json = self._jsonify(obj)
        return json, 'text/javascript'

    def _jsonify(self, obj):
        """Convert a Python object to a JSON string.

        The object, ``obj``, must be "simple"--that is, it may consist of only
        tuples, list, dicts, numbers, and strings (and other built-in types,
        too?).

        """
        return simplejson.dumps(obj)

    def _set_wrap(self, value=None):
        """Set whether to wrap a template in its parent template.

        If ``value`` is given, use that value. If ``wrap`` is set in
        ``request.params``, convert its value to ``bool`` and use that value.
        Otherwise, set ``self.wrap`` to True.

        ``value``
            ``bool`` indicating whether or not a template should be wrapped in
            its inherited templates. ``wrap`` gets passed along to the
            template, which can decide to do whatever it wants with the
            ``wrap`` setting.

        """
        if value is not None:
            self.wrap = value
        else:
            wrap = request.params.get('wrap', 'true').strip().lower()
            if wrap in ('0', 'n', 'no', 'false', 'nil'):
                self.wrap = False
            else:
                self.wrap = True
