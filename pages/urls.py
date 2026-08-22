from django.urls import path

from .views import HomeView, OfferView, PrivacyView

app_name = 'pages'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('pages/offer/', OfferView.as_view(), name='offer'),
    path('pages/privacy/', PrivacyView.as_view(), name='privacy'),
]
