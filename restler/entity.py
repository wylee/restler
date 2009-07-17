"""Entity base class and metaclass.

The :class:`Entity` class here should be used as the base class for any and
all entity classes, regardless of what database the entities are derived from.

Ditto for the :class:`EntityMeta` class, which should be used as the basis
for all SQLAlchemy declarative entities (which will probably be *all*
entities).

"""
import datetime
import decimal
import json

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
    def all(cls, filters=None, start=None, offset=None, limit=None):
        """Get "all" records of this entity type, possibly filtered.

        Note that the name `all` is somewhat of a misnomer. This method
        should perhaps be named `collection` or `some`.

        ``filters`` is a list of objects that are suitable within a SQLAlchemy
        Session filter. These can be strings or SA constructs.

        ``offset`` and ``start`` have the same meaning--SQL OFFSET as used by,
        e.g., Postgres. ``start`` is here just to make certain ExtJS AJAX
        queries easier.

        ``limit`` limits the number of items returned to the specified number.

        0 is a valid value for ``offset`` and ``limit``, so special handling
        is required when checking to see if they have been passed.

        """
        start = None if start == '' else start
        offset = None if offset == '' else offset
        limit = None if limit == '' else limit
        q = cls.get_db_session().query(cls)
        for f in filters or []:
            q = q.filter(f)
        offset = offset if offset is not None else start
        if offset is not None:
            q = q.offset(int(offset))
        if limit is not None:
            q = q.limit(int(limit))
        collection = q.all()
        return collection

    @classmethod
    def simplify_object(cls, obj):
        """Convert ``obj`` to something JSON encoder can handle."""
        try:
            obj = obj.to_simple_object()
        except AttributeError:
            pass
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
