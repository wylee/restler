from elixir import metadata, Entity, has_field, has_many, belongs_to
from elixir import String, Integer


class Directory(Entity):
    """A `Directory` contains `Page`s."""
    has_field('title', String(40))
    has_field('slug', String(20))
    has_many('pages', of_kind='Page')


class Page(Entity):
    """A `Page` belongs to a `Directory`."""
    has_field('title', String(40))
    has_field('slug', String(20))
    has_field('content', String)
    has_field('sidebar', String)
    belongs_to('directory', of_kind='Directory')
