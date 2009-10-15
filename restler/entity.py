"""Entity base class and metaclass.

The :class:`Entity` class here should be used as the base class for any and
all entity classes, regardless of what database the entities are derived from.

Ditto for the :class:`EntityMeta` class, which should be used as the basis
for all SQLAlchemy declarative entities (which will probably be *all*
entities).

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
        """Convert this object into a simplified form that can be JSONified.

        ``fields`` is a list of pairs of (attribute name, mapped name). If
        this arg isn't given, ``self.public_names`` is used instead.

        """
        obj = dict(type=self.__class__.__name__)
        if fields is None:
            fields = [(f, f) for f in self.public_names]
        for name, as_name in fields:
            name_parts = name.split('.')
            o = self
            for n in name_parts:
                o = getattr(o, n)
            val = self.simplify_object(o, n)
            if name == as_name:
                # If `name` has only one part, this sets obj[name] = val.
                # If `name` had more than N parts, this sets
                # obj[name1][name2][...][nameN] = val.
                slot = obj
                for n in name_parts[:-1]:
                    slot = slot.setdefault(n, {})
                slot[name_parts[-1]] = val
            else:
                # Use user-specified name
                obj[as_name] = val
        return obj

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

    def get_column_default(self, key):
        """Get default set in SQLA table (NOT server default)."""
        default = self.__table__.columns.get(key).default.arg
        return default

    @property
    def public_names(self):
        """We want all public DB columns and `property`s by default."""
        try:
            self._public_names
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
            self._public_names = names
        return self._public_names

    def __str__(self):
        names = sorted(self.public_names)
        title = self.member_title
        string = [title, '-' * len(title)]
        string += ['%s: %s' % (name, getattr(self, name)) for name in names]
        return '\n'.join(string)


class EntityMeta(type):

    def __init__(cls, name, bases, attrs):
        """Add member/collection related class attributes to ``Entity`` classes.

        Classes of this type are instrumented with ``member_name``,
        ``collection_name``, ``member_title``, and ``collection_title`` class
        attributes, IFF these class attributes are not already set in the
        class definition.

        """
        type.__init__(cls, name, bases, attrs)
        underscore_name = camel_to_underscore(cls.__name__)
        cls.member_name = getattr(cls, 'member_name', underscore_name)
        cls.collection_name = getattr(
            cls, 'collection_name', '%ss' % underscore_name)
        cls.member_title = getattr(
            cls, 'member_title', underscore_to_title(cls.member_name))
        cls.collection_title = getattr(
            cls, 'collection_title', underscore_to_title(cls.collection_name))
