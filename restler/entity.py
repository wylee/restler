"""Entity base class.

The :class:`Entity` class here should be used as the base class for any and
all entity classes, regardless of what database the entities are derived from.

"""
import datetime
import decimal
try:
    import json
except ImportError:
    import simplejson as json

from string import ascii_uppercase

from sqlalchemy import Column
from sqlalchemy.orm import class_mapper


datetime_types = (datetime.time, datetime.date, datetime.datetime)


def underscore_to_title(name):
    return name.replace('_', ' ').title()


def camel_to_underscore(name):
    for char in ascii_uppercase:
        name = name.replace(char, '_%s' % char)
    name = name.lower()
    name = name.strip('_')
    return name


class Entity(object):

    @property
    def id(self):
        pk = self._sa_instance_state.key
        if pk is None:
            return None
        vals = pk[1]
        if len(vals) == 1:
            return vals[0]
        else:
            return tuple(vals)

    @property
    def id_str(self):
        """Convert `id` from Python to string."""
        if isinstance(self.id, basestring):
            id = self.id
        else:
            id = json.dumps(self.simplify_object(self.id))
        return id

    @classmethod
    def str_to_id(cls, id):
        """Convert ``id`` from string to Python.

        If `id` is scalar, return ``id`` as is; if it's a list, assume it's
        JSON encoded and decode it.

        """
        if cls.has_multipart_primary_key():
            id = json.loads(id)
            if not isinstance(id, list):
                raise ValueError(
                    'Expected a string that could be parsed as a multi-part '
                    'primary key. Something like `(1, "a")`')
        return id

    @classmethod
    def has_multipart_primary_key(cls):
        try:
            cls._has_multipart_primary_key
        except AttributeError:
            pk = class_mapper(cls).primary_key
            cls._has_multipart_primary_key = (True if (len(pk) > 1) else False)
        return cls._has_multipart_primary_key

    @classmethod
    def convert_param(self, name, val):
        return val

    @classmethod
    def simplify_object(cls, obj, name=None):
        """Convert ``obj`` to something JSON encoder can handle."""
        try:
            obj.to_simple_object
        except AttributeError:
            pass
        else:
            obj = obj.to_simple_object()
        if isinstance(obj, (list, tuple)):
            obj = [cls.simplify_object(i) for i in obj]
        elif isinstance(obj, decimal.Decimal):
            f, i = float(obj), int(obj)
            obj = i if f == i else f
        elif isinstance(obj, datetime_types):
            obj = str(obj)
        return obj

    def to_simple_object(self, fields=None):
        """Convert and return simplified form of `self` that can be JSONified.

        See :meth:`_parse_fields_for_simple_object` for description of
        ``fields``.

        """
        obj = dict(
            __module__=self.__class__.__module__,
            __type__=self.__class__.__name__,
        )
        include_fields = self._parse_fields_for_simple_object(fields)
        for name, as_name in include_fields:
            name_parts = name.split('.')
            o = self
            for n in name_parts:
                o = getattr(o, n)
            val = self.simplify_object(o, n)
            if name == as_name:
                # If `name` has only one part, this sets obj[name] = val.
                # If `name` has more than one part (N parts), this sets
                # obj[name1][name2][...][nameN] = val.
                slot = obj
                for n in name_parts[:-1]:
                    slot = slot.setdefault(n, {})
                slot[name_parts[-1]] = val
            else:
                # Use user-specified name
                obj[as_name] = val
        return obj

    def _parse_fields_for_simple_object(self, fields):
        """Parse ``fields`` and return the set of fields to be included.

        Each item in the returned set will be a 2-tuple mapping an Entity
        instance attribute name to another name. The mapped name might be the
        same as the attribute name::

            {('attr1', 'attr1'), ('attr2', 'different_name'), ...}

        ``fields`` is a list of attributes to include and/or exclude in the
        returned object object. If ``fields`` is `None`, the default set of
        fields will be used; (the list of names returned by
        :meth:`_public_names`).

        When ``fields`` is *not* `None`, the special value "*" can be given as
        one of the list items to indicate that the default set of fields
        should be used. In this case, "+" and "-" fields (see below) will be
        included or excluded relative to the default set.

        Each item in the list may be either a string or a dict. A string is
        used to indicate that an attribute's name should be used as-is in the
        response.

        A dict is used to map the field's column name to a different name
        in the response. In this case, the dict must contain a ``name`` key
        with the field's column name and a ``mapping`` key with the name
        desired in the reponse.

        In either case, the first character of the attribute name may be a "+"
        or a "-". These are used to, respectively, include or exclude fields
        from the result object. "-my_attr" used with "*" is an easy way to say
        "Everything but my_attr." "+my_attr" used with "*" is an easy way
        (the *only* way!) to include fields that aren't part of the default
        set (for example, relations are never included by default).

        """
        if fields is None:
            fields = ['*']
        elif isinstance(fields, dict):
            # Support legacy dict format wherein every field is mapped to
            # a name, even if it's the same name.
            fields = [dict(name=k, mapping=v) for k, v in fields.items()]
        mapped_fields = []
        include_fields = set()
        exclude_fields = set()
        for item in fields:
            if isinstance(item, basestring):
                name, as_name = item, item
            elif isinstance(item, dict):
                name, as_name = item['name'], item['mapping']
            if name.startswith('-'):
                exclude_fields.add(name.lstrip('-'))
            elif name == '*':
                mapped_fields += [(n, n) for n in self._public_names]
            else:
                # Note that unprefixed fields and fields prefixed with "+"
                # have the same semantics, and that's why we always strip
                # leading "+"s here.
                mapped_fields.append((name.lstrip('+'), as_name.lstrip('+')))
        for name, as_name in mapped_fields:
            if name not in exclude_fields:
                include_fields.add((name, as_name))
        return include_fields

    def to_json(self, fields=None):
        return json.dumps(self.to_simple_object(fields=fields))

    @classmethod
    def to_simple_collection(cls, collection, fields=None):
        try:
            collection[0].to_simple_object
        except AttributeError:
            # Assume collection of `RowTuple`s
            dicts = []
            for m in collection:
                keys = m.keys()
                vals = (getattr(m, k) for k in keys)
                dicts.append(dict(zip(keys, vals)))
            return [cls.simplify_object(d) for d in dicts]
        else:
            # Assume collection of instances of a mapped class
            return [m.to_simple_object(fields) for m in collection]

    @classmethod
    def to_json_collection(cls, collection=None, fields=None):
        simple_obj = cls.to_simple_collection(collection, fields=fields)
        return json.dumps(simple_obj)

    @property
    def _public_names(self):
        """We want all public DB columns and `property`s by default."""
        try:
            self.__public_names
        except AttributeError:
            names = []
            class_attrs = self.__class__.__dict__
            for name in class_attrs:
                if name.startswith('_'):
                    continue
                attr = class_attrs[name]
                if isinstance(attr, property):
                    names.append(name)
                else:
                    try:
                        clause_el = attr.__clause_element__()
                    except AttributeError:
                        pass
                    else:
                        if issubclass(clause_el.__class__, Column):
                            names.append(name)
            names = set(names)
            self.__public_names = names
        return self.__public_names

    def __str__(self):
        names = sorted(self._public_names)
        title = self.member_title
        string = [title, '-' * len(title)]
        string += ['%s: %s' % (name, getattr(self, name)) for name in names]
        return '\n'.join(string)


def instrument_class(cls, mixin=Entity):
    """Add member/collection class attributes to `Entity` subclass ``cls``.

    ``cls`` will be instrumented with ``member_name``, ``collection_name``,
    ``member_title``, and ``collection_title`` class attributes, IFF these
    class attributes are not already set in the class definition.

    In addition, ``mixin`` will be dynamically inserted into ``cls``'s
    list of base classes. ``mixin`` must be :class:`Entity` or a subclass
    (although this isn't currently enforced). ``mixin`` can also be `None`
    to completely disable this "feature" (XXX: Should this be the default?).

    """
    if not hasattr(cls, 'member_name'):
        cls.member_name = camel_to_underscore(cls.__name__)
    if not hasattr(cls, 'collection_name'):
        cls.collection_name = '{0}s'.format(cls.member_name)
    if not hasattr(cls, 'member_title'):
        cls.member_title = underscore_to_title(cls.member_name)
    if not hasattr(cls, 'collection_title'):
        cls.collection_title = underscore_to_title(cls.collection_name)
    if mixin is not None and mixin not in cls.__bases__:
            cls.__bases__ += (mixin,)
    return cls
