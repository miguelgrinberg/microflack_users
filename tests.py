#!/usr/bin/env python
import os
os.environ['FLASK_CONFIG'] = 'test'

import mock
import time
import unittest

from microflack_common.auth import generate_token
from microflack_common.test import FlackTestCase

from app import app, db, User


class UserTests(FlackTestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()  # just in case
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_user(self):
        # get users without auth
        r, s, h = self.get('/api/users')
        self.assertEqual(s, 200)

        # get users with bad auth
        r, s, h = self.get('/api/users', token_auth='bad-token')
        self.assertEqual(s, 401)

        # create a new user
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'bar'})
        self.assertEqual(s, 201)
        url = h['Location']

        # create a duplicate user
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'baz'})
        self.assertEqual(s, 400)

        # create an incomplete user
        r, s, h = self.post('/api/users', data={'nickname': 'foo1'})
        self.assertEqual(s, 400)

        # request a token
        token = generate_token(1)

        # get user
        r, s, h = self.get(url)
        self.assertEqual(s, 200)
        self.assertEqual(r['nickname'], 'foo')
        self.assertEqual('http://localhost' + r['_links']['self'], url)
        self.assertEqual(r['_links']['tokens'], '/api/tokens')

        # modify nickname
        r, s, h = self.put(url, data={'nickname': 'foo2'}, token_auth=token)
        self.assertEqual(s, 204)

        # create second user
        r, s, h = self.post('/api/users', data={'nickname': 'bar',
                                                'password': 'baz'})
        self.assertEqual(s, 201)
        url2 = h['Location']

        # edit second user with first user token
        r, s, h = self.put(url2, data={'nickname': 'bar2'}, token_auth=token)
        self.assertEqual(s, 403)

        # check new nickname
        r, s, h = self.get(url)
        self.assertEqual(r['nickname'], 'foo2')

        # get list of users
        r, s, h = self.get('/api/users')
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 2)

    def test_user_online_offline(self):
        # create a couple of users and a token
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'foo'})
        self.assertEqual(s, 201)
        r, s, h = self.post('/api/users', data={'nickname': 'bar',
                                                'password': 'bar'})
        self.assertEqual(s, 201)
        r, s, h = self.get('/api/users/me', basic_auth='foo:foo')
        self.assertEqual(s, 200)
        token = generate_token(1)

        # update online status
        User.find_offline_users()

        # get list of offline users
        r, s, h = self.get('/api/users?online=0', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'bar')

        # get list of online users
        r, s, h = self.get('/api/users?online=1', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'foo')

        # alter last seen time of the two users
        user = User.query.filter_by(nickname='foo').first()
        user.last_seen_at = int(time.time()) - 65
        db.session.add(user)
        user = User.query.filter_by(nickname='bar').first()
        user.last_seen_at = int(time.time()) - 1000
        db.session.add(user)
        db.session.commit()

        # update online status
        User.find_offline_users()

        # get list of offline users
        r, s, h = self.get('/api/users?online=0', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'bar')

        # get list of online users (only foo, who owns the token)
        r, s, h = self.get('/api/users?online=1', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'foo')

        # get users updated since a timestamp
        since = r['users'][0]['updated_at']
        with mock.patch('app.time.time', return_value=since + 10):
            r, s, h = self.get('/api/users?updated_since=' + str(since + 2),
                               token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'foo')

        # update the other user
        user = User.query.filter_by(nickname='bar').first()
        user.password = 'bar2'
        db.session.add(user)
        db.session.commit()

        # get updated users again
        with mock.patch('app.time.time', return_value=since + 10):
            r, s, h = self.get('/api/users?updated_since=' + str(since - 1),
                               token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 2)
        self.assertEqual(r['users'][0]['nickname'], 'bar')
        self.assertEqual(r['users'][1]['nickname'], 'foo')


if __name__ == '__main__':
    unittest.main(verbosity=2)
