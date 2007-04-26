from pylons import Response, c, request
from pylons.controllers import WSGIController
from pylons.templating import render, render_response
from pylons.helpers import abort, redirect_to
from pylons.util import class_name_from_module_name
from pylons.database import create_engine

from webhelpers.pagination import paginate

import mako
import sqlalchemy
import elixir
import simplejson

__all__ = ['options', 'BaseController', 'init_model']


TemplateNotFoundExceptions = (mako.exceptions.TopLevelLookupException,)

options = dict(
    per_page=10,
    template_path='defaults',
    html_file_extension='html',
)


def BaseController(the_model, the_parent_model=None):
    """``BaseController`` class factory.

    Each generated ``BaseController`` class has ``the_model`` and
    ``the_parent_model`` attached to it. If ``parent_model`` is not specified,
    it defaults to ``the_model`` (i.e., normally, the model for a resource
    and its parent are the same).

    """
    init_model(the_model)
    if the_parent_model is None:
        the_parent_model = the_model
    else:
        if the_parent_model is not the_model:
            init_model(the_parent_model)

    class BaseController(WSGIController):
        """Base class for RESTful controllers."""

        _model = the_model
        _parent_model = the_parent_model

        def __init__(self):
            """Initialize RESTful Controller.

            It is assumed that the controller file is named after the
            resource's collection name and that there is a corresponding top
            level template directory. For example, for a Hat resource, the
            controller file will be named hats.py and there will be a template
            directory at /templates/hats.

            """
            del self._model.session_context.current
            if self._parent_model is not self._model:
                del self._parent_model.session_context.current

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

            self.parent_resource = route.parent_resource

            self._init_entity()
            self._init_parent_entity(route_info)
            self._create_properties()

        def _init_entity(self):
            # Import entity class for resource
            self.entity_name = class_name_from_module_name(self.member_name)
            self.Entity = getattr(self._model, self.entity_name)

        def _init_parent_entity(self, route_info):
            # Do setup for parent resource, if this resource is nested
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
                name = class_name_from_module_name(self.parent_member_name)
                self.parent_entity_name = name
                self.ParentEntity = getattr(self._parent_model, name)

                self._set_parent_by_id(self.parent_id)

                if (hasattr(self, 'Entity') and 
                    self.Entity.c.get(self.parent_id_name, None) is not None):
                    self.has_fk_to_parent = True
                else:
                    self.has_fk_to_parent = False
            else:
                self.is_nested = False
                self.has_fk_to_parent = False

        def _create_properties(self):
            # Create aliases for the generically named properties (``member``,
            # ``parent``, etc), using the resource and its parent's actual
            # names. For example, if the resource's member name is "cat", the
            # property ``cat`` will be created. It will correspond to the
            # generically named property ``member``.
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

            Show a form for editing an existing item that has ID ``id``. The
            form should PUT to /resource/update (but since PUT is not
            well-supported, we use POST with a hidden input field to indicate
            it's really a PUT).

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
            if self.is_nested and self.has_fk_to_parent:
                setattr(self.member, self.parent_id_name, self.parent_id)
            self.member.flush()
            self.member.refresh()

        def _redirect_to_member(self):
            args = {'id': self.member.id, 'action': 'show',
                    'format': self.format}
            if self.is_nested and self.has_fk_to_parent:
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
            if self.is_nested and self.has_fk_to_parent:
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
            self._set_property(('collection', self.collection_name),
                               collection)
        collection = property(_get_collection, _set_collection)

        def _get_member(self):
            return self.__dict__.get('member', None)
        def _set_member(self, member):
            self._set_property(('member', self.member_name), member)
        member = property(_get_member, _set_member)

        def _set_parent_by_id(self, parent_id):
            self.parent = self._get_entity_or_404(self.ParentEntity,
                                                  parent_id)

        def _set_member_by_id(self, id):
            args = {}
            if self.is_nested and self.has_fk_to_parent:
                args[self.parent_id_name] = self.parent.id
            self.member = self._get_entity_or_404(self.Entity, id, **args)

        def _get_entity_or_404(self, Entity, id, **kwargs):
            """Get entity with ID ``id``

            ``Entity``
                The entity class to select from

            ``id``
                The entity's ID

            ``kwargs``
                Other column name/value pairs used to narrow the select. This
                is used internally by ``_set_member_by_id`` to filter the
                select if there's a parent resource (e.g., kwargs =
                {'parent_id': 123}).

            """
            entity = None
            if hasattr(Entity, 'alternate_ids'):
                ids = Entity.alternate_ids
                for alt_id in ids:
                    kwargs[alt_id] = id
                    entity = Entity.get_by(**kwargs)
                    kwargs.pop(alt_id)
                    if entity is not None:
                        break
            elif 'slug' in Entity.c:
                entity = Entity.get_by(slug=id, **kwargs)
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

        def _set_collection_by_id(self):
            args = {}
            entity = self.Entity
            page = request.params.get('page', 0)
            try:
                page = int(page)
            except (ValueError, TypeError):
                page = 0
            if page < 0:
                page = 0
            per_page = request.params.get('per_page', options['per_page'])
            try:
                per_page = int(per_page)
            except (ValueError, TypeError):
                per_page = options['per_page']
            if per_page < 1:
                per_page = 1
            args.update(dict(
                page=page,
                per_page=per_page,
                order_by=[entity.c.id],
            ))
            if self.is_nested and self.has_fk_to_parent:
                col = entity.c[self.parent_id_name]
                args['query_args'] = [col == self.parent.id]
            self.paginator, self.collection = paginate(entity, **args)

        def _render_response(self, format=None, template=None, wrap=None,
                             **response_args):
            """Render a response for those actions that return content.

            ``format``
                An alternative format for the response content; by default,
                ``format`` from ``request.params`` is used

            ``template``
                An alternative template; by default, a template named after
                the action is used

            ``wrap``
                A ``bool`` indicating whether or not to "wrap" a template in
                its inherited templates(s). This is an alternative wrap
                setting; by default, the wrap setting comes from
                ``request.params``.

            ``response_args``
                The remaining keyword args will be passed to the ``Response``
                costructor

            return ``Response``

            """
            # Dynamically determine the content method
            format = (format or self.format or 'html').strip().lower()
            _get_content = getattr(self, '_get_%s_content' % (format))

            # _get_<format>_content methods need to add file extension (if
            # needed)
            template = (template or self.template or self.action)
            self._template_path = self.collection_name
            self._template_name = template

            if wrap is not None:
                self.wrap = wrap

            content, mimetype = _get_content()
            response_args.update(dict(content=content, mimetype=mimetype))
            response = Response(**response_args)
            return response

        def _render(self, extension):
            args = [self._template_path, self._template_name, extension]
            try:
                return render('/%s/%s.%s' % tuple(args))
            except TemplateNotFoundExceptions:
                args[0] = options['template_path']
                return render('mako', '/%s/%s.%s' % tuple(args))

        def _get_html_content(self):
            """Get HTML content and mimetype."""
            content = self._render(options['html_file_extension'])
            return content, 'text/html'

        def _get_text_content(self):
            """Get plain text content and mimetype."""
            content = self._render('txt')
            return content, 'text/plain'
        _get_txt_content = _get_text_content

        def _get_xml_content(self):
            """Get XML content."""
            content = self._render('xml')
            return content, 'text/xml'

        def _get_json_content(self, block=None):
            """Get a JSON string and mimetype "text/javascript".

            Assumes members have a ``to_builtin`` method that returns an
            object that can be JSONified by the ``simplejson module``. That
            object is JSONified and returned unless the ``block`` arg is
            supplied.

            ``block``
                This method creates the simplest possible object to be
                JSONified (``obj``) by calling ``to_builtin`` on a member or
                members. If a function is passed via ``block``, that function
                will be called with ``obj``, and ``obj`` can be modified there
                before being JSONified here.

            """
            if self.collection is not None:
                obj = [m.to_builtin() for m in self.collection]
            elif self.member is not None:
                obj = self.member.to_builtin()
            else:
                obj = None
            if block is not None:
                obj = block(obj)
            json = self._jsonify(obj)
            return json, 'text/javascript'

        def _jsonify(self, obj):
            """Convert a Python object to a JSON string.

            The object, ``obj``, must be "simple"--that is, it may consist of
            only tuples, list, dicts, numbers, and strings (and other built-in
            types, too?).

            """
            return simplejson.dumps(obj)

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
                self.wrap = value
            else:
                wrap = request.params.get('wrap', 'true').strip().lower()
                if wrap in ('0', 'n', 'no', 'false', 'nil'):
                    self.wrap = False
                else:
                    self.wrap = True

    return BaseController


def init_model(model, **engine_args):
    """Initialize a ``model``.

    ``model``
        Module containing mapped entity classes; these may be either
        ``Elixir`` entities or classes mapped with ``assign_mapper``

    ``engine_args``
        Keyword args to pass through to ``create_engine``
            ``uri`` -- database connection string
            ``echo`` -- whether to echo SQL statements

    """
    # SQLAlchemy metadata. Prefer metadata defined in ``model``
    metadata = getattr(model, 'metadata', elixir.metadata)

    try:
        # SQLAlchemy database engine. Prefer engine defined in ``model``
        engine = getattr(model, 'engine', create_engine(**engine_args))
    except TypeError:
        # This happens when ``model`` doesn't define ``engine`` and
        # ``create_engine`` gets called--the Pylons ``create_engine`` only
        # works when the site is running because it magically gets the DB
        # config from INI file the site is running under.
        import sys
        sys.stderr.write('WARNING: Database engine was not defined in '
                         '``model`` and could not be created.\n')
        engine = None
    else:
        if not metadata.is_bound():
            metadata.connect(engine)

    session_context = getattr(model, 'session_context',
                              elixir.objectstore.context)

    model.engine = engine
    model.metadata = metadata
    model.session_context = session_context
