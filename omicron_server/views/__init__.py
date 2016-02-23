"""
Contains the endpoints for the API, created as pluggable objects using
`Flask RESTful<https://flask-restful-cn.readthedocs.org/en/0.3.4/>`_.

"""
from omicron_server.views.schema_defined_resource import SchemaDefinedResource
from omicron_server.views.projects import Projects, ProjectContainer
from omicron_server.views.users import UserContainer, UserView
__author__ = 'Michal Kononenko'
