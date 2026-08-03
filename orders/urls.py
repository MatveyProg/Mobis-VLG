from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.cart_detail, name='cart'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:pk>/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('history/', views.OrderListView.as_view(), name='order_list'),
    path('history/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('active/', views.ActiveOrdersView.as_view(), name='active_orders'),
    path('active/<int:pk>/status/', views.active_order_set_status, name='active_order_set_status'),
]
