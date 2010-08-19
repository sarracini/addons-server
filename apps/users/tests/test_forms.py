from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.http import int_to_base36

import test_utils
from manage import settings
from mock import patch
from nose.tools import eq_

import amo.test_utils
from amo.helpers import urlparams
from amo.urlresolvers import reverse
from users.models import UserProfile


class UserFormBase(amo.test_utils.ExtraSetup, test_utils.TestCase):

    fixtures = ['users/test_backends']

    def setUp(self):
        self.user = User.objects.get(id='4043307')
        self.user_profile = self.user.get_profile()
        self.uidb36 = int_to_base36(self.user.id)
        self.token = default_token_generator.make_token(self.user)


class TestSetPasswordForm(UserFormBase):

    def _get_reset_url(self):
        return "/en-US/firefox/users/pwreset/%s/%s" % (self.uidb36, self.token)

    def test_url_fail(self):
        r = self.client.get('/users/pwreset/junk/', follow=True)
        eq_(r.status_code, 404)

        r = self.client.get('/en-US/firefox/users/pwreset/%s/12-345' %
                                                                self.uidb36)
        self.assertContains(r, "Password reset unsuccessful")

    def test_set_fail(self):
        url = self._get_reset_url()
        r = self.client.post(url, {'new_password1': '', 'new_password2': ''})
        self.assertFormError(r, 'form', 'new_password1',
                                   "This field is required.")
        self.assertFormError(r, 'form', 'new_password2',
                                   "This field is required.")

        r = self.client.post(url, {'new_password1': 'one',
                                   'new_password2': 'two'})
        self.assertFormError(r, 'form', 'new_password2',
                                   "The two password fields didn't match.")

    def test_set_success(self):
        url = self._get_reset_url()

        assert self.user_profile.check_password('testo') is False

        self.client.post(url, {'new_password1': 'testo',
                               'new_password2': 'testo'})

        self.user_profile = User.objects.get(id='4043307').get_profile()

        assert self.user_profile.check_password('testo')


class TestPasswordResetForm(UserFormBase):

    def test_request_fail(self):
        r = self.client.post('/en-US/firefox/users/pwreset',
                            {'email': 'someemail@somedomain.com'})

        eq_(len(mail.outbox), 0)
        self.assertFormError(r, 'form', 'email',
                             ("That e-mail address doesn't have an "
                              "associated user account. Are you sure "
                              "you've registered?"))

    def test_request_success(self):
        self.client.post('/en-US/firefox/users/pwreset',
                        {'email': self.user.email})

        eq_(len(mail.outbox), 1)
        assert mail.outbox[0].subject.find('Password reset') == 0
        assert mail.outbox[0].body.find('pwreset/%s' % self.uidb36) > 0


class TestUserDeleteForm(UserFormBase):

    def test_bad_password(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'password': 'wrong', 'confirm': True, }
        r = self.client.post('/en-US/firefox/users/delete', data)
        msg = "Wrong password entered!"
        self.assertFormError(r, 'form', 'password', msg)

    def test_not_confirmed(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'password': 'foo'}
        r = self.client.post('/en-US/firefox/users/delete', data)
        self.assertFormError(r, 'form', 'confirm', 'This field is required.')

    def test_success(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'password': 'foo', 'confirm': True, }
        r = self.client.post('/en-US/firefox/users/delete', data, follow=True)
        self.assertContains(r, "Profile Deleted")
        u = UserProfile.objects.get(id='4043307')
        eq_(u.email, '')


class TestUserEditForm(UserFormBase):

    def test_no_names(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'username': '',
                'email': 'jbalogh@mozilla.com', }
        r = self.client.post('/en-US/firefox/users/edit', data)
        msg = "This field is required."
        self.assertFormError(r, 'form', 'username', msg)

    def test_no_real_name(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'username': 'blah',
                'email': 'jbalogh@mozilla.com', }
        r = self.client.post('/en-US/firefox/users/edit', data, follow=True)
        self.assertContains(r, "Profile Updated")

    def test_set_wrong_password(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'email': 'jbalogh@mozilla.com',
                'oldpassword': 'wrong',
                'password': 'new',
                'password2': 'new', }
        r = self.client.post('/en-US/firefox/users/edit', data)
        self.assertFormError(r, 'form', 'oldpassword',
                                                'Wrong password entered!')

    def test_set_unmatched_passwords(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'email': 'jbalogh@mozilla.com',
                'oldpassword': 'foo',
                'password': 'new1',
                'password2': 'new2', }
        r = self.client.post('/en-US/firefox/users/edit', data)
        self.assertFormError(r, 'form', 'password2',
                                            'The passwords did not match.')

    def test_set_new_passwords(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        data = {'username': 'jbalogh',
                'email': 'jbalogh@mozilla.com',
                'oldpassword': 'foo',
                'password': 'new',
                'password2': 'new', }
        r = self.client.post('/en-US/firefox/users/edit', data, follow=True)
        self.assertContains(r, "Profile Updated")


class TestUserLoginForm(UserFormBase):

    def _get_login_url(self):
        return "/en-US/firefox/users/login"

    def test_credential_fail(self):
        url = self._get_login_url()
        r = self.client.post(url, {'username': '', 'password': ''})
        self.assertFormError(r, 'form', 'username', "This field is required.")
        self.assertFormError(r, 'form', 'password', "This field is required.")

        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'wrongpassword'})
        self.assertFormError(r, 'form', '', ("Please enter a correct username "
                                             "and password. Note that both "
                                             "fields are case-sensitive."))

    def test_credential_success(self):
        url = self._get_login_url()
        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'foo'}, follow=True)
        self.assertContains(r, "Welcome, Jeff Balogh")
        self.assertTrue(self.client.session.get_expire_at_browser_close())

        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'foo',
                                   'rememberme': 1}, follow=True)
        self.assertContains(r, "Welcome, Jeff Balogh")
        # Subtract 100 to give some breathing room
        age = settings.SESSION_COOKIE_AGE - 100
        assert self.client.session.get_expiry_age() > age

    def test_redirect_after_login(self):
        url = urlparams(self._get_login_url(), to="en-US/firefox/about")
        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'foo'}, follow=True)
        self.assertRedirects(r, '/en-US/firefox/about')

    def test_redirect_after_login_evil(self):
        "http://foo.com is a bad value for redirection."
        url = urlparams(self._get_login_url(), to="http://foo.com")
        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'foo'}, follow=True)
        self.assertRedirects(r, '/en-US/firefox/')

    def test_unconfirmed_account(self):
        url = self._get_login_url()
        self.user_profile.confirmationcode = 'blah'
        self.user_profile.save()
        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'foo'}, follow=True)
        self.assertNotContains(r, "Welcome, Jeff")
        self.assertContains(r, "A link to activate your user account")
        self.assertContains(r, "If you did not receive the confirmation")

    def test_disabled_account(self):
        url = self._get_login_url()
        self.user_profile.deleted = True
        self.user_profile.save()
        r = self.client.post(url, {'username': 'jbalogh@mozilla.com',
                                   'password': 'foo'}, follow=True)
        self.assertNotContains(r, "Welcome, Jeff")
        self.assertContains(r, 'Please enter a correct username and password. '
                               'Note that both fields are case-sensitive.')


class TestUserRegisterForm(UserFormBase):

    def test_no_info(self):
        data = {'email': '',
                'password': '',
                'password2': '',
                'username': '', }
        r = self.client.post('/en-US/firefox/users/register', data)
        msg = "This field is required."
        self.assertFormError(r, 'form', 'email', msg)
        self.assertFormError(r, 'form', 'username', msg)

    def test_register_existing_account(self):
        data = {'email': 'jbalogh@mozilla.com',
                'password': 'xxx',
                'password2': 'xxx',
                'username': 'xxx', }
        r = self.client.post('/en-US/firefox/users/register', data)
        self.assertFormError(r, 'form', 'email',
                             'User profile with this Email already exists.')
        eq_(len(mail.outbox), 0)

    def test_set_unmatched_passwords(self):
        data = {'email': 'john.connor@sky.net',
                'password': 'new1',
                'password2': 'new2', }
        r = self.client.post('/en-US/firefox/users/register', data)
        self.assertFormError(r, 'form', 'password2',
                                            'The passwords did not match.')
        eq_(len(mail.outbox), 0)

    def test_invalid_username(self):
        data = {'email': 'testo@example.com',
                'password': 'xxx',
                'password2': 'xxx',
                'username': 'IE6Fan', }
        r = self.client.post('/en-US/firefox/users/register', data)
        self.assertFormError(r, 'form', 'username',
                             'This username is invalid.')

    def test_already_logged_in(self):
        self.client.login(username='jbalogh@mozilla.com', password='foo')
        r = self.client.get('/users/register', follow=True)
        self.assertContains(r, "You are already logged in")
        self.assertNotContains(r, '<button type="submit">Register</button>')

    @patch('captcha.fields.ReCaptchaField.clean')
    def test_success(self, clean):
        clean = lambda: ''

        data = {'email': 'john.connor@sky.net',
                'password': 'carebears',
                'password2': 'carebears',
                'username': 'BigJC',
                'homepage': ''}
        r = self.client.post('/en-US/firefox/users/register', data,
                             follow=True)
        self.assertContains(r, "Congratulations!")

        u = User.objects.get(email='john.connor@sky.net').get_profile()

        assert u.confirmationcode
        eq_(len(mail.outbox), 1)
        assert mail.outbox[0].subject.find('Please confirm your email') == 0
        assert mail.outbox[0].body.find('%s/confirm/%s' %
                                        (u.id, u.confirmationcode)) > 0


class TestBlacklistedUsernameAdminAddForm(UserFormBase):

    def test_no_usernames(self):
        self.client.login(username='testo@example.com', password='foo')
        url = reverse('admin:users_blacklistedusername_add')
        data = {'usernames': "\n\n", }
        r = self.client.post(url, data)
        msg = 'Please enter at least one username to blacklist.'
        self.assertFormError(r, 'form', 'usernames', msg)

    def test_add(self):
        self.client.login(username='testo@example.com', password='foo')
        url = reverse('admin:users_blacklistedusername_add')
        data = {'usernames': "IE6Fan\nfubar\n\n", }
        r = self.client.post(url, data)
        msg = '1 new usernames added to the blacklist. '
        msg += '1 duplicates were ignored.'
        self.assertContains(r, msg)
        self.assertNotContains(r, 'fubar')
