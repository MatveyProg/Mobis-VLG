from django.urls import path

from . import views

app_name = 'warehouse'

urlpatterns = [
    path('stock/', views.stock_balances, name='stock_balances'),
    # Заявки на закупку
    path('requisitions/', views.requisition_list, name='requisition_list'),
    path('requisitions/new/', views.requisition_create, name='requisition_create'),
    path('requisitions/from-sales/', views.requisition_from_sales, name='requisition_from_sales'),
    path('requisitions/<int:pk>/', views.requisition_detail, name='requisition_detail'),
    path('requisitions/<int:pk>/export/', views.requisition_export, name='requisition_export'),
    path('requisitions/<int:pk>/status/', views.requisition_set_status, name='requisition_set_status'),
    path('requisitions/<int:pk>/items/add/', views.requisition_add_item, name='requisition_add_item'),
    path(
        'requisitions/<int:pk>/items/<int:item_pk>/delete/',
        views.requisition_delete_item,
        name='requisition_delete_item',
    ),
    path('requisitions/<int:pk>/receive/', views.requisition_receive, name='requisition_receive'),
    # Приходы
    path('stock-in/', views.stock_in_list, name='stock_in_list'),
    path('stock-in/new/', views.stock_in_create, name='stock_in_create'),
    path('stock-in/<int:pk>/', views.stock_in_detail, name='stock_in_detail'),
    path('stock-in/<int:pk>/items/add/', views.stock_in_add_item, name='stock_in_add_item'),
    path(
        'stock-in/<int:pk>/items/<int:item_pk>/delete/',
        views.stock_in_delete_item,
        name='stock_in_delete_item',
    ),
    path('stock-in/<int:pk>/post/', views.stock_in_post, name='stock_in_post'),
]
