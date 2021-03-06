from tests import TestCaseWithAppContext
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid1
import mock
from freezegun import freeze_time
from sqlalchemy import create_engine
from omicron_server.config import default_config as conf
from omicron_server.database.schema import metadata
import omicron_server

__author__ = 'Michal Kononenko'


class TestToken(TestCaseWithAppContext):
    engine = create_engine('sqlite://')
    time_to_freeze = datetime.utcnow()

    def setUp(self):
        TestCaseWithAppContext.setUp(self)
        self.token_string = str(uuid1())
        self.expiration_date = self.time_to_freeze + timedelta(seconds=1800)


class TestTokenConstructor(TestToken):

    def setUp(self):
        TestToken.setUp(self)
        self.token_string = 'foobarbaz123456'

    @freeze_time(TestToken.time_to_freeze)
    @mock.patch('omicron_server.models.users.Token.hash_token')
    def test_constructor_with_expiration_date(self, mock_hash_token):

        token = omicron_server.models.users.Token(
                self.token_string, self.expiration_date
        )
        self.assertIsInstance(
                token, omicron_server.models.users.Token
        )

        self.assertEqual(self.expiration_date, token.expiration_date)
        self.assertEqual(self.time_to_freeze, token.date_created)

        self.assertEqual(
            mock.call(self.token_string), mock_hash_token.call_args
        )

    @freeze_time(TestToken.time_to_freeze)
    @mock.patch('omicron_server.models.users.Token.hash_token')
    def test_constructor_no_expiration_date(self, mock_hash):

        token = omicron_server.models.users.Token(self.token_string)
        expiration_date = self.time_to_freeze + timedelta(
                seconds=conf.DEFAULT_TOKEN_EXPIRATION_TIME
        )

        self.assertEqual(expiration_date, token.expiration_date)
        self.assertTrue(mock_hash.called)

    @freeze_time(TestToken.time_to_freeze)
    @mock.patch('omicron_server.models.users.Token.hash_token')
    @mock.patch('uuid.UUID.__str__', return_value=str(uuid1()))
    def test_construtor_uuid_token(self, mock_uuid_str, mock_hash):
        """
        Tests that the constructor converts tokens of :class:``uuid.UUID``
        into strings by using the ``str()`` function

        :param mock.MagicMock mock_uuid_str: A mock call to the uuid string
            function
        :param mock.MagicMock mock_hash: A mock object representing a call to
            the token hasher. Injected dynamically with the ``mock.patch``
            decorator
        """

        token = omicron_server.models.users.Token(uuid1())

        self.assertIsInstance(token, omicron_server.models.users.Token)
        self.assertTrue(mock_uuid_str.called)
        self.assertTrue(mock_hash.called)


class TestHashToken(TestToken):
    def setUp(self):
        TestToken.setUp(self)
        self.token = omicron_server.models.Token(self.token_string)

    @mock.patch('omicron_server.models.users.sha256')
    def test_hash_token(self, mock_sha256):
        mock_sha256.return_value = sha256('foobarbaz123456'.encode('ascii'))
        self.token.hash_token(self.token_string)

        hash_call = mock.call(self.token_string.encode('ascii'))

        self.assertEqual(
            hash_call, mock_sha256.call_args
        )


class TestVerifyToken(TestToken):
    def setUp(self):
        TestToken.setUp(self)
        self.token = omicron_server.models.users.Token(self.token_string)

    @freeze_time(TestToken.time_to_freeze)
    @mock.patch('omicron_server.models.users.Token.hash_token')
    def test_verify_token(self, mock_hash):
        mock_hash.return_value = self.token.token_hash

        self.token.expiration_date = self.time_to_freeze - timedelta(seconds=1)
        self.assertGreater(self.time_to_freeze, self.token.expiration_date)

        self.assertFalse(self.token.verify_token(self.token_string))

        self.assertFalse(mock_hash.called)

        self.token.expiration_date = self.time_to_freeze + timedelta(seconds=1)
        self.assertLess(self.time_to_freeze, self.token.expiration_date)

        self.assertTrue(self.token.verify_token(self.token_string))

        self.assertTrue(mock_hash.called)

    @freeze_time(TestToken.time_to_freeze)
    @mock.patch('sqlalchemy.orm.Session.add')
    def test_revoke_token(self, mock_add):
        self.token.revoke()
        self.assertEqual(self.token.expiration_date, self.time_to_freeze)
        self.assertEqual(mock.call(self.token), mock_add.call_args)


class TestFromDatabaseSession(TestToken):
    """
    Tests :meth:`Token.from_database_session`
    """
    def setUp(self):
        TestToken.setUp(self)
        self.session = omicron_server.database.ContextManagedSession(
                bind=conf.DATABASE_ENGINE
        )
        self.token = uuid1()
        self.token_record = omicron_server.models.Token(
            str(self.token), expiration_date=self.expiration_date
        )

    @mock.patch('sqlalchemy.orm.Query.first')
    def test_constructor_uuid(self, mock_first):
        mock_first.return_value = self.token_record

        token = omicron_server.models.Token.from_database_session(
            self.token, self.session
        )

        self.assertEqual(token, self.token_record)

    @mock.patch('sqlalchemy.orm.Query.first')
    def test_constructor_string(self, mock_first):
        mock_first.return_value = self.token_record

        token = omicron_server.models.Token.from_database_session(
            self.token_string, self.session
        )

        self.assertEqual(token, self.token_record)


class TestUser(TestCaseWithAppContext):
    engine = create_engine('sqlite://')

    def setUp(self):
        TestCaseWithAppContext.setUp(self)
        self.username = 'scott'
        self.password = 'tiger'
        self.email = 'scott@tiger.com'
        self.base_session = \
            omicron_server.database.sessions.ContextManagedSession(
                bind=self.engine
            )

    @classmethod
    def tearDownClass(cls):
        metadata.drop_all(bind=cls.engine)
        TestCaseWithAppContext.tearDownClass()


class TestUserConstructor(TestUser):

    @mock.patch('omicron_server.models.users.User.hash_password')
    def test_constructor(self, mock_hash_function):

        mock_hash_function.return_value = 'hashed_password'

        user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.assertIsInstance(user, omicron_server.models.users.User)
        self.assertEqual(user.username, self.username)
        self.assertEqual(user.email_address, self.email)
        self.assertEqual(user.password_hash, mock_hash_function.return_value)

        mock_hash_function_call = mock.call(self.password)
        self.assertEqual(mock_hash_function.call_args, mock_hash_function_call)


class TestFromSession(TestUser):

    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(
                self.username, self.password, self.email
        )
        self.bad_user = [self.user, 'another list']

        self.assertFalse(isinstance(self.bad_user, self.user.__class__))

    @mock.patch('sqlalchemy.orm.Query.first')
    def test_from_session(self, mock_first):
        mock_first.return_value = self.user
        self.assertEqual(
            self.user,
            self.user.__class__.from_session(self.username, self.base_session)
        )
        self.assertTrue(mock_first.called)

    @mock.patch('sqlalchemy.orm.Query.first')
    def test_from_session_throws_typerror(self, mock_first):
        mock_first.return_value = self.bad_user
        with self.assertRaises(TypeError):
            self.user.__class__.from_session(self.username, self.base_session)

        self.assertTrue(mock_first.called)


class TestHashPassword(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(self.username,
                                                     self.password, self.email)

    @mock.patch('omicron_server.models.users.pwd_context.encrypt')
    def test_hash_password(self, mock_encrypt):
        self.assertEqual(
            mock_encrypt.return_value,
                omicron_server.models.users.User.hash_password(self.password)
        )

        mock_encrypt_call = mock.call(self.password)
        self.assertEqual(
            mock_encrypt_call, mock_encrypt.call_args
        )


class TestVerifyPassword(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.bad_password = 'invalid'

        self.assertNotEqual(self.password, self.bad_password)

    def test_verify_good_password(self):
        self.assertTrue(self.user.verify_password(self.password))

    def test_verify_bad_password(self):
        self.assertFalse(self.user.verify_password(self.bad_password))


class TestGenerateAuthToken(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(
                self.username, self.password, self.email
        )
        self.mock_token_return_value = uuid1()

    def tearDown(self):
        TestUser.tearDown(self)

    @mock.patch('sqlalchemy.orm.Session.add')
    @mock.patch('omicron_server.models.users.uuid1')
    def test_generate_auth_token(self, mock_guid, mock_add):
        mock_guid.return_value = self.mock_token_return_value

        token = self.user.generate_auth_token()[0]
        self.assertEqual(str(self.mock_token_return_value), token)

        self.assertTrue(mock_guid.called)
        self.assertTrue(mock_add.called)

    @mock.patch('sqlalchemy.orm.Session.add')
    @mock.patch('omicron_server.models.users.uuid1')
    @freeze_time('2012-01-01')
    def test_generate_auth_token_default_date(
            self, mock_guid, mock_add
    ):
        mock_guid.return_value = self.mock_token_return_value
        _, expiration_date = self.user.generate_auth_token()
        self.assertEqual(
            expiration_date,
            datetime.utcnow() + timedelta(
                    seconds=conf.DEFAULT_TOKEN_EXPIRATION_TIME
            )
        )


class TestVerifyAuthToken(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.mock_token ='foobarbaz123456'

    @mock.patch('omicron_server.models.users.User.current_token')
    def test_verify_token(self, mock_token):
        self.user.verify_auth_token(self.mock_token)
        self.assertEqual(
            mock.call(self.mock_token),
            mock_token.verify_token.call_args
        )


class TestCurrentToken(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.token_string = 'foobarbaz123456'
        self.user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.mock_token = omicron_server.models.users.Token(self.token_string)

    @mock.patch('sqlalchemy.orm.Query.order_by')
    def test_current_token(self, mock_order):
        self.assertIsNotNone(self.user.current_token)
        self.assertTrue(mock_order.called)


class TestGet(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.expected_result = {
            'username': self.username,
            'email': self.email,
            'date_created': self.user.date_created.isoformat()
        }

    def test_get(self):
        self.assertEqual(self.expected_result, self.user.get)


class TestGetFull(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.expected_result = {
            'username': self.username,
            'email': self.email,
            'date_created': self.user.date_created.isoformat(),
            'projects': []
        }

    def test_get_full(self):
        self.assertEqual(self.expected_result, self.user.get_full)


class TestUserRepr(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(self.username, self.password, self.email)
        self.expected_result = '%s(%s, %s, %s)' % (
            self.user.__class__.__name__, self.username,
            self.user.password_hash, self.email
        )

    def test_repr(self):
        self.assertEqual(self.expected_result, self.user.__repr__())


class TestEqandNe(TestUser):
    def setUp(self):
        TestUser.setUp(self)
        self.user = omicron_server.models.users.User(
            self.username, self.password, self.email
        )
        self.other_user = omicron_server.models.users.User(
            'foo', 'bar', 'foo@bar.com'
        )

        self.identical_user = omicron_server.models.users.User(
            self.username, self.password, self.email
        )

    def test_eq(self):
        self.assertTrue(self.user == self.identical_user)
        self.assertFalse(self.user == self.other_user)

    def test_ne(self):
        self.assertTrue(self.user != self.other_user)
        self.assertFalse(self.user != self.identical_user)
