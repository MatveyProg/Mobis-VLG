from django.views.generic import TemplateView


class OfferView(TemplateView):
    template_name = 'pages/offer.html'


class PrivacyView(TemplateView):
    template_name = 'pages/privacy.html'
