from tests import TestCaseWithAppContext
import unittest
import jsonschema
import mock
from omicron_server.views import AbstractResource, SchemaDefinedResource
from omicron_server import app

__author__ = 'Michal Kononenko'


class ResourceWithoutSchema(AbstractResource):
    def get(self):
        return 'Gotten'


class TestAbstractResource(TestCaseWithAppContext):
    @classmethod
    def setUpClass(cls):
        TestCaseWithAppContext.setUpClass()
        cls.view = ResourceWithoutSchema()


class TestAbstractResourceOptions(TestAbstractResource):
    def setUp(self):
        TestAbstractResource.setUp(self)
        self.assertEqual(self.view.get(), 'Gotten')

    def test_options(self):
        with self.context:
            self.assertEqual(
                self.view.options().status_code, 200
            )


class ResourceWithSchema(SchemaDefinedResource):
    schema = {
      "$schema": "http://json-schema.org/draft-04/schema#",
      "id": "http://jsonschema.net",
      "type": "object",
      "properties": {
        "entry": {
          "id": "http://jsonschema.net/entry",
          "type": "string"
        }
      },
      "required": [
        "entry"
      ]
    }


class TestAPIViewWithSchema(TestCaseWithAppContext):
    @classmethod
    def setUpClass(cls):
        cls.view = ResourceWithSchema()
        cls.context = app.test_request_context()


class TestAPIViewWithSchemaConstructor(TestAPIViewWithSchema):
    def setUp(self):
        TestCaseWithAppContext.setUp(self)
        self.view.show_schema = mock.MagicMock()
        self.view.get = mock.MagicMock()

    def test_view_constructor(self):
        self.view.__init__()
        self.assertTrue(self.view.show_schema.called)


class TestParseQueryString(TestAPIViewWithSchema):

    def test_parse_string_none_return_false(self):
        self.assertFalse(self.view._should_show_schema(None))

    def test_parse_query_string_returns_true(self):
        self.assertTrue(self.view._should_show_schema('true'))
        self.assertTrue(self.view._should_show_schema('True'))

    def test_parse_query_string_false_return(self):
        self.assertFalse(self.view._should_show_schema('false'))
        self.assertFalse(self.view._should_show_schema('False'))

    @mock.patch('omicron_server.views.abstract_resource.abort')
    def test_parse_query_string_404_abort(self, mock_abort):
        mock_abort_call = mock.call(404)

        self.view._should_show_schema('Should return 404')

        self.assertEqual(mock_abort_call, mock_abort.call_args)


class TestShowSchema(TestAPIViewWithSchema):

    @staticmethod
    def _method_to_decorate():
        return True

    @mock.patch(
            'omicron_server.views.SchemaDefinedResource._should_show_schema',
            return_value=True)
    @mock.patch('omicron_server.views.abstract_resource.jsonify')
    @mock.patch('omicron_server.views.abstract_resource.request')
    def test_show_schema_true(self, mock_request, mock_jsonify, mock_q_string):
        func = self.view.show_schema(self._method_to_decorate)

        self.assertTrue(func())
        self.assertEqual(
            mock.call(self.view.schema),
            mock_jsonify.call_args
        )
        self.assertTrue(mock_q_string.called)
        self.assertTrue(mock_request.args.get.called)

    @mock.patch(
            'omicron_server.views.SchemaDefinedResource._should_show_schema',
            return_value=False)
    @mock.patch('omicron_server.views.abstract_resource.jsonify')
    @mock.patch('omicron_server.views.abstract_resource.request')
    def test_show_schema_false(self, mock_request, mock_jsonify, mock_parse):
        func = self.view.show_schema(self._method_to_decorate)

        self.assertTrue(func())

        self.assertFalse(mock_jsonify.called)

        self.assertTrue(mock_parse.called)


class TestValidateSchema(TestAPIViewWithSchema):
    def setUp(self):
        TestAPIViewWithSchema.setUp(self)
        self.valid_dict = {'entry': 'this is a string'}
        self.valid_dict_schema = {
            'entry':
                {'type': 'string', 'pattern': '/entry/'}
        }

    @mock.patch(
            'omicron_server.views.abstract_resource.jsonschema.validate'
    )
    def test_validate_dict_true(self, mock_validate):

        self.assertTrue(self.view.validate(self.valid_dict))
        self.assertEqual(
            mock.call(self.valid_dict, self.view.schema),
            mock_validate.call_args
        )

    @mock.patch(
            'omicron_server.views.abstract_resource.jsonschema.validate',
            side_effect=jsonschema.ValidationError('test error')
    )
    def test_validate_dict_false(self, mock_validate):

        self.assertFalse(self.view.validate(self.valid_dict)[0])
        self.assertTrue(mock_validate.called)

    @mock.patch(
            'omicron_server.views.abstract_resource.jsonschema.validate'
    )
    def test_validate_dict_custom_schema(self, mock_validate):

        self.assertTrue(
                self.view.validate(self.valid_dict, self.valid_dict_schema)
        )

        self.assertEqual(
            mock.call(self.valid_dict, self.valid_dict_schema),
            mock_validate.call_args
        )


class TestSchemaDefinedResourceOptions(TestAPIViewWithSchema):
    def test_options(self):
        with self.context:
            self.assertEqual(self.view.options().status_code, 200)
