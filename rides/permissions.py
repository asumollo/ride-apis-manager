from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from rides.models import User

if TYPE_CHECKING:
    from rest_framework.views import APIView


class IsAdminRole(BasePermission):
    message = "Only users with the admin role can access this API."

    def has_permission(self, request: Request, view: "APIView") -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
