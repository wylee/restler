import unittest

import pylons
from routes.mapper import Mapper
from routes.util import URLGenerator
from webob import Request
from webob.exc import HTTPSeeOther

from restler import Controller, Entity


class Fields_for_Simple_Object(unittest.TestCase):

    def setUp(self):
        self.entity = Entity()
        self.default_set = set([('id', 'id'), ('id_str', 'id_str')])

    def should_be_default_set_when_input_is_None(self):
        fields = self.entity._parse_fields_for_simple_object(None)
        self.assertEqual(fields, self.default_set)

    def should_be_default_set_when_input_is_glob(self):
        fields = self.entity._parse_fields_for_simple_object(['*'])
        self.assertEqual(fields, self.default_set)

    def should_include_extra_fields_when_specified(self):
        fields = self.entity._parse_fields_for_simple_object(
            ['*', '+_public_names'])
        expected_fields = self.default_set.union(
            set([('_public_names', '_public_names')]))
        self.assertEqual(fields, expected_fields)

    def should_exclude_specified_fields(self):
        fields = self.entity._parse_fields_for_simple_object(['*', '-id_str'])
        expected_fields = self.default_set - set([('id_str', 'id_str')])
        self.assertEqual(fields, expected_fields)

    def should_work_with_legacy_dict_format(self):
        fields = self.entity._parse_fields_for_simple_object({
            '*': '*',
            'a': 'a',
            '+b': 'B',
            'b': 'B',
            '-id_str': '-id_str'
        })
        expected_fields = self.default_set.union(set([('a', 'a'), ('b', 'B')]))
        expected_fields -= set([('id_str', 'id_str')])
        self.assertEqual(fields, expected_fields)


class TmplContext(object): pass

class TestRedirection(unittest.TestCase):

    def setUp(self):
        self.mapper = Mapper()
        self.mapper.resource('thing', 'things')

    def _get_controller_for_request(self, path='/things/x', **kwargs):
        request = Request.blank(path, **kwargs)
        request.script_name = '/script'
        pylons.request._push_object(request)
        pylons.url._push_object(URLGenerator(self.mapper, request.environ))
        pylons.tmpl_context._push_object(TmplContext())
        controller = Controller()
        controller.controller = 'things'
        controller.format = 'json'
        return controller

    def test_redirect(self):
        controller = self._get_controller_for_request()
        url_args = dict(action='show', id='x')
        try:
            controller._do_redirect(url_args)
        except HTTPSeeOther as e:
            assert e.location == '/script/things/x.json'

    def test_xhr(self):
        controller = self._get_controller_for_request()
        url_args = dict(action='show', id='x')
        try:
            controller._do_redirect(url_args)
        except HTTPSeeOther as e:
            assert e.location == '/script/things/x.json'

    def test_xhr_with_client_request_url(self):
        controller = self._get_controller_for_request(headers={
            'X-Requested-With': 'XMLHttpRequest',
            'X-Restler-Client-Request-URL': 'http://tntest.trimet.org/script',
        })
        url_args = dict(action='show', id='x')
        try:
            controller._do_redirect(url_args)
        except HTTPSeeOther as e:
            assert e.location == 'http://tntest.trimet.org/script/things/x.json'


class TestController(unittest.TestCase):
    pass
