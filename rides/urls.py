from rest_framework.routers import DefaultRouter

from rides.views import RideEventViewSet, RideViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet)
router.register("rides", RideViewSet)
router.register("ride-events", RideEventViewSet)

urlpatterns = router.urls
