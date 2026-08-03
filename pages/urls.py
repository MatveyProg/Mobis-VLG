from django.urls import path

from .views import OfferView, PrivacyView

app_name = 'pages'

urlpatterns = [
    path('offer/', OfferView.as_view(), name='offer'),
    path('privacy/', PrivacyView.as_view(), name='privacy'),
]
