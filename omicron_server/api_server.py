"""
Defines the flask app which will run our HTTP application. This also creates
a flask-restful API object, which will serve as the router to the objects in
:mod:`api_views`.
"""
import logging
from flask import Flask, g, jsonify, request, abort
from flask_restful import Api
from .auth import auth
from .config import default_config as conf
from .database import Administrator, User, ContextManagedSession, Token
from .decorators import crossdomain
from .views import UserContainer, UserView, ProjectContainer
from .views import Projects

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

__author__ = 'Michal Kononenko'

app = Flask(__name__)
api = Api(app, prefix='/api/v1', decorators=[crossdomain(origin='*')])

api.add_resource(UserContainer, '/users')
api.add_resource(UserView, '/users/<username_or_id>')
api.add_resource(ProjectContainer, '/projects')
api.add_resource(Projects, 'projects/<project_name_or_id>')

database_session = ContextManagedSession(bind=conf.DATABASE_ENGINE)


@app.route('/', methods=["GET", "OPTIONS"])
@app.route('/index', methods=["GET", "OPTIONS"])
@crossdomain(origin='*')
def hello_world():
    """
    Base URL to confirm that the API actually works. Eventually, this endpoint
    will serve the OmicronClient_. JavaScript UI to users.

    **Example Response**

    .. sourcecode:: http

        GET / HTTP/1.1
        Content-Type: application/json

        Hello World!

    .. _OmicronClient: https://github.com/MichalKononenko/OmicronClient

    :return: Hello, world!
    :rtype: str
    """
    return jsonify({'message': 'hello_world'})


@app.route('/api/v1/token', methods=['POST', 'OPTIONS'])
@crossdomain(origin='*')
@auth.login_required
def create_token():
    """
    Generate a user's auth token from the user in Flask's :attr:`Flask.g`
    object, which acts as an object repository unique to each request. Expects
    an Authorization header with Basic Auth.

    **Example Request**

    .. sourcecode:: http

        POST /api/v1/token HTTP/1.1
        Host: example.com
        Content-Type: application/json
        Authorization: B12kS1l2jS1=

    **Example Response**

    .. sourcecode:: http

        Content-Type: application/json

        {
            "token": "a409a362-d733-11e5-b625-7e14f79230d0",
            "expiration_date": "2015-01-01T12:00:00"
        }

    :statuscode 201: The token was created successfully
    :statuscode 401: The token could not be created because the user tried to
        authenticate with

    :return: A Flask response object with the token jsonified into ASCII
    """
    if g.authenticated_from_token:
        abort(401)
    try:
        token, expiration_date = g.user.generate_auth_token(
            expiration=int(request.args.get('expiration'))
        )
    except TypeError:
        log.debug('No expiration supplied, using default expiration time')
        token, expiration_date = g.user.generate_auth_token()
    response = jsonify(
            {'token': token,
             'expiration_date': expiration_date.isoformat()
             }
    )
    response.status_code = 201
    return response


@app.route('/api/v1/token', methods=['DELETE'])
@crossdomain(origin='*')
@auth.login_required
def revoke_token():
    """
    Revoke the current token for the user that has just authenticated,
    or the user with username given by a query parameter, allowed only if the
    user is an Administrator.

    **Example Request**

    .. sourcecode:: http

        DELETE /api/v1/token HTTP/1.1
        Content-Type: application/json
        Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=

        {
            "token": "f7f55e52-89a6-40f7-b5ad-2fff0d1871b7"
        }

    **Example Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {"message": "token deleted successfully"}
    """
    if not g.authenticated_from_token:
        _handle_token_logout(request, g.user)

    username_to_delete = request.args.get('username')
    if username_to_delete is None:
        username_to_delete = g.user.username
    else:
        username_to_delete = str(username_to_delete)

    if isinstance(g.user, Administrator):
        with database_session() as session:
            user = session.query(
                User
            ).filter_by(
                username=username_to_delete
            ).first()
            if user is None:
                abort(403)
            user.current_token.first().revoke()
    else:
        with database_session() as session:
            session.query(g.user.__class__).filter_by(
                id=g.user.id
            ).first().current_token.first().revoke()

    response = jsonify({'token_status': 'deleted'})
    return response


@database_session()
def _handle_token_logout(req_to_parse, user_to_logout, session):
    request_data = req_to_parse.json
    if request_data is None:
        abort(400)

    try:
        token_to_revoke = request_data['token']
    except KeyError:
        response = jsonify(
                {'error': "request body does not contain token"}
        )
        response.status_code = 400

        return response

    token_record = Token.from_database_session(token_to_revoke, session)

    if token_record is None:
        response = jsonify({
            'error': "unable to find required token"
        })
        response.status_code = 400
        return response

    if token_record.owner == g.user or isinstance(g.user, Administrator):
        token_record.revoke()

        response = jsonify({'message': 'token revoked successfully'})

    else:
        response = jsonify(
            {'error': 'attempted unauthorized token revocation'}
        )
        response.status_code = 403

    return response
