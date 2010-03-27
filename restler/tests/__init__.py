import unittest

from restler.entity import Entity


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


class TestController(unittest.TestCase):
    pass
