"""Restler helper functions."""
from webhelpers import link_to, button_to, url, tag
from webhelpers import text_field, text_area, check_box
from sqlalchemy import types

__all__ = [
    'make_nav_menu',
    'make_nav_list',
    'nav_list_for_resource',
    'nav_list_for_collection',
    'nav_list_for_member',
    'form_field_for_col',
    'nice_name_for_col',
    'get_prev_next_per_page',
]


type_to_field = {
    types.AbstractType: text_field,
    types.BLOB: text_field,
    types.BOOLEAN: check_box,
    types.Binary: text_field,
    types.Boolean: text_field,
    types.CHAR: text_field,
    types.CLOB: text_field,
    types.DATE: text_field,
    types.DATETIME: text_field,
    types.DECIMAL: text_field,
    types.Date: text_field,
    types.DateTime: text_field,
    types.FLOAT: text_field,
    types.Float: text_field,
    types.INT: text_field,
    types.INTEGER: text_field,
    types.Integer: text_field,
    types.MutableType: text_field,
    types.NCHAR: text_field,
    types.NULLTYPE: text_field,
    types.NullTypeEngine: text_field,
    types.Numeric: text_field,
    types.PickleType: text_field,
    types.SMALLINT: text_field,
    types.SmallInteger: text_field,
    types.Smallinteger: text_field,
    types.String: text_field,
    types.TEXT: text_area,
    types.TIME: text_field,
    types.TIMESTAMP: text_field,
    types.Time: text_field,
    types.TypeDecorator: text_field,
    types.TypeEngine: text_field,
    types.Unicode: text_field,
    types.VARCHAR: text_field,
}
max_cols = 40
default_rows = 5
string_types = (types.CHAR, types.String, types.Unicode,
                  types.VARCHAR)
small_int_types = (types.SMALLINT, types.SmallInteger,
                     types.Smallinteger)
int_types = (types.INT, types.INTEGER, types.Integer)


def make_nav_menu(context, id='nav', menu_class='menu'):
    lists = nav_list_for_resource(context)
    return make_nav_list(lists, id, menu_class)


def make_nav_list(lists, id='nav', menu_class='menu'):
    """Create a list of lists, where the list items are links.

    ``lists``
        A list of lists of {a: link, **li_tag_attrs}
        E.g., [[{'a': '<a href="url">link</a>', attrs for <li>}, ...], ...]

        The generated <ul> has id="nav" unless overridden by ``id``. The inner
        <ul>s have class="menu" unless overridden by ``menu_class``. The first
        and last <li>s in a menu have, respectively, class="first" and
        class="last".

    """
    result = ['<ul id="%s">' % id]
    for items in lists:
        last = len(items) - 1
        result += ['<li>', '<ul class="%s">' % menu_class]
        for i, item in enumerate(items):
            a = item.pop('a')
            if i == 0:
                item['class_'] = (item.get('class_', '') + ' first').strip()
            if i == last:
                item['class_'] = (item.get('class_', '') + ' last').strip()
            result += [tag('li', open=True, **item), a, '</li>']
        result += ['</ul>', '</li>']
    result.append('</ul>')
    return ''.join(result)


def nav_list_for_resource(context):
    lists = []
    if context.is_nested:
        parent = context.parent
        p_name = context.parent_member_name
        p_link_text = 'Up to Parent %s' % p_name.title()
        url_args = {'id': parent.id}
        gp_m_name = context.grandparent_member_name
        if gp_m_name:
            gp_id_name = '%s_id' % gp_m_name
            p_url = '%s_%s' % (gp_m_name, p_name)
            grandparent_id = getattr(parent, gp_id_name)
            url_args[gp_id_name] = grandparent_id
        else:
            p_url = p_name
        lists.append([{'a': link_to(p_link_text, url(p_url, **url_args))}])
        url_args = {'parent_name': p_name, 'parent_id': parent.id}
    else:
        url_args = {}
    m_name = context.member_name
    member = context.member
    resource_list = nav_list_for_collection(m_name, **url_args)
    if context.action != 'new' and member:
        resource_list += nav_list_for_member(m_name, member.id, **url_args)
    lists.append(resource_list)
    return lists


def nav_list_for_collection(member_name, parent_name=None, parent_id=None):
    if parent_name is not parent_id is not None:
        url_args = {'%s_id' % parent_name: parent_id}
        list_url = '%s_%s' % (parent_name, member_name)
        new_url = '%s_new_%s' % (parent_name, member_name)
    else:
        url_args = {}
        list_url = '%s' % member_name
        new_url = 'new_%s' % member_name
    list_link_text = '%s List' % member_name.title()
    new_link_text = 'New %s' % member_name.title()
    return [
        {'a': link_to(list_link_text, url(list_url, **url_args))},
        {'a': link_to(new_link_text, url(new_url, **url_args))},
    ]


def nav_list_for_member(member_name, member_id, parent_name=None,
                        parent_id=None, terse_link_text=False,
                        join_with=None):
    if parent_name is not parent_id is not None:
        url_args = {'id': member_id, '%s_id' % parent_name: parent_id}
        show_url = '%s_%s' % (parent_name, member_name)
        edit_url = '%s_edit_%s' % (parent_name, member_name)
        delete_url = '%s_%s' % (parent_name, member_name)
    else:
        url_args = {'id': member_id}
        show_url = '%s' % member_name
        edit_url = 'edit_%s' % member_name
        delete_url = '%s' % member_name
    m_name_title = member_name.title()
    if terse_link_text:
        show_link_text = 'Show'
        edit_link_text = 'Edit'
        delete_link_text = 'Delete'
    else:
        show_link_text = 'Show %s' % m_name_title
        edit_link_text = 'Edit %s' % m_name_title
        delete_link_text = 'Delete %s' % m_name_title
    links = [
        {'a': link_to(show_link_text, url(show_url, **url_args),
                      title='Show %s details' % member_name)},
        {'a': link_to(edit_link_text, url(edit_url, **url_args),
                      title='Edit %s details' % member_name)},
        {'a': button_to(delete_link_text, url(delete_url, **url_args),
                        method='DELETE', confirm='Really delete this item?',
                        title='Remove %s from database' % member_name)},
    ]
    if join_with is not None:
        links = [link['a'] for link in links]
        links = ' &middot; '.join(links)
    return links


def form_field_for_col(col, member, **kw):
    """Return a form field corresponding to the type of column ``col``.

    ``member``
        A member object of some resource

    """
    col_name = col.key
    col_type = col.type
    value = getattr(member, col_name, '')
    field_maker = type_to_field.get(col_type, text_field)
    field_args = {}
    length = getattr(col_type, 'length', 0)
    if (field_maker is text_field and
        isinstance(col_type, string_types) and
        (length > max_cols or length is None)):
        field_maker = text_area
    if field_maker is text_field:
        if isinstance(col_type, string_types):
            field_args['size'] = min(max_cols, length) or max_cols
        elif isinstance(col_type, int_types):
            field_args['size'] = 10
        elif isinstance(col_type, small_int_types):
            field_args['size'] = 5
    elif field_maker is text_area:
        field_args.update({'rows': default_rows, 'cols': max_cols})
    elif field_maker is check_box:
        if isinstance(col_type, types.BOOLEAN):
            field_args['checked'] = value
    # User's args override any args calculated here
    field_args.update(kw)
    form_field = field_maker(col_name, value, **field_args)
    return form_field


def nice_name_for_col(col):
    """Return a nice, readable name for the column ``col``.

    Replace "_" and "-" with " " and title-ize. Assumes column names use
    under_score or sl-ug style. [Question: is slug-style legal for table
    names?]

    """
    replacements = {' ': '_-'}
    name = col.name
    for new_val in replacements:
        old_vals = replacements[new_val]
        for o in old_vals:
            name = name.replace(o, new_val)
    name = name.title()
    return name


def get_prev_next_per_page(paginator):
    """Return previous and next page numbers and number of items per page.

    ``paginator``
        Object containing pagination data, typically from a call to
        ``webhelpers.pagination.paginate``, but could be any object with
        ``current_page``, ``items_per_page``, and ``item_count`` attributes.

    """
    page = paginator.current_page
    per_page = paginator.items_per_page
    item_count = paginator.item_count
    prev_page = page - 1
    if prev_page < 0:
        prev_page = 0
    next_page = page + 1
    last_page = item_count / per_page
    if (item_count % per_page) == 0:
        last_page -= 1
    if next_page > last_page:
        next_page = last_page
    return prev_page, next_page, per_page


def print_attrs(obj):
    for a in dir(obj):
        if not a.startswith('_'):
            print a
