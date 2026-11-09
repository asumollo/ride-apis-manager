from django.test import TestCase

from rides.models import User


class UserManagerTests(TestCase):
    """
    How users are created outside the API
    """

    def test_superuser_gets_admin_role(self):
        user = User.objects.create_superuser("boss", "boss@example.com", "pass12345!")
        self.assertEqual(user.role, User.Role.ADMIN)
