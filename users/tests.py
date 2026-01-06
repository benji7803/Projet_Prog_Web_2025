from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthViewsTests(TestCase):
    def setUp(self):
        self.username = "alice"
        self.password = "s3cr3tPass!"
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.login_url = reverse('users:login')
        self.logout_url = reverse('users:logout')
        self.dashboard_url = reverse('templates:dashboard')

    def test_login_post_logs_in(self):
        """
        Test that posting valid credentials to the login view logs in the user.
        
        :param self: Description
        """
        resp = self.client.post(self.login_url, {'username': self.username, 'password': self.password}, follow=True)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertTrue(resp.context['user'].is_authenticated)

    def test_login_get_shows_form(self):
        """
        Test that a GET request to the login view returns the login form.
        
        :param self: Description
        """
        resp = self.client.get(self.login_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('<form', resp.content.decode())

    def test_logout_post_logs_out_and_redirects(self):
        self.client.login(username=self.username, password=self.password)
        resp = self.client.post(self.logout_url, follow=True)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(resp.context['user'].is_anonymous)

    def test_logout_get_not_allowed(self):
        resp = self.client.get(self.logout_url)
        self.assertEqual(resp.status_code, 405)