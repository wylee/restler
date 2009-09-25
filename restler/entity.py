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

    @classmethod
    def simplify_object(cls, obj):
        """Convert ``obj`` to something JSON encoder can handle."""
        try:
            obj.to_simple_object
        except AttributeError:
            pass
        else:
            obj = obj.to_simple_object()
        if isinstance(obj, decimal.Decimal):
            f, i = float(obj), int(obj)
            obj = i if f == i else f
        elif isinstance(obj, datetime_types):
            obj = str(obj)
        return obj

    def to_simple_object(self, fields=None):
        obj = dict(type=self.__class__.__name__)
        names = fields or self.public_names
        for name in names:
            val = getattr(self, name)
            val = self.simplify_object(val)
            obj[name] = val
        return obj

    def to_json(self, fields=None):
        return json.dumps(self.to_simple_object(fields=fields))

    @classmethod
    def to_simple_collection(cls, collection=None, fields=None):
        if collection is None:
            collection = cls.get_db_session().query(cls)
        return [i.to_simple_object(fields=fields) for i in collection]

    @classmethod
    def to_json_collection(cls, collection=None, fields=None):
        simple_obj = cls.to_simple_collection(collection, fields=fields)
        return json.dumps(simple_obj)

    def get_column_default(self, key):
        default = self.__table__.columns.get(key).default
        if default is None:
            return default
        else:
            return cls.get_db_session().execute(default)

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
