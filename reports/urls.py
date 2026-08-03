from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('stock-in/', views.report_stock_in, name='stock_in'),
    path('stock-out/', views.report_stock_out, name='stock_out'),
    path('balances/', views.report_balances, name='balances'),
    path('movement/', views.report_movement, name='movement'),
]
