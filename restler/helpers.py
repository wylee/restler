"""Restler helper functions."""
from webhelpers import link_to, button_to, url, tag

__all__ = ['make_nav_menu',
           'make_nav_list',
           'nav_list_for_resource',
           'nav_list_for_collection',
           'nav_list_for_member']


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
        p_link_text = 'Up to %s "%s"' % (p_name.title(), parent.title)
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
                        parent_id=None):
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
    show_link_text = 'Show %s' % m_name_title
    edit_link_text = 'Edit %s' % m_name_title
    delete_link_text = 'Delete %s' % m_name_title
    return [
        {'a': link_to(show_link_text, url(show_url, **url_args))},
        {'a': link_to(edit_link_text, url(edit_url, **url_args))},
        {'a': button_to(delete_link_text, url(delete_url, **url_args),
                        style='display: inline', method='DELETE',
                        confirm='Are you sure?')},
    ]
