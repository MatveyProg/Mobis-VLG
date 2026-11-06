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
    path('requests/', views.ClientRequestListView.as_view(), name='client_request_list'),
    path('requests/draft/', views.client_request_draft, name='client_request_draft'),
    path('requests/inbox/', views.ClientRequestInboxView.as_view(), name='client_request_inbox'),
    path('requests/add/<int:pk>/', views.client_request_add, name='client_request_add'),
    path('requests/item/<int:pk>/update/', views.client_request_update_item, name='client_request_update_item'),
    path('requests/item/<int:pk>/remove/', views.client_request_remove_item, name='client_request_remove_item'),
    path('requests/<int:pk>/', views.ClientRequestDetailView.as_view(), name='client_request_detail'),
    path('requests/<int:pk>/review/', views.client_request_review, name='client_request_review'),
]
