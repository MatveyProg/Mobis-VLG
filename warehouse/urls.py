from django.urls import path

from . import views

app_name = 'warehouse'

urlpatterns = [
    path('stock/', views.stock_balances, name='stock_balances'),
]
