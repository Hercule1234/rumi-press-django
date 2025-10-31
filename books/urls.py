from django.urls import path
from . import views

urlpatterns = [
    # Catégories
    path('', views.category_list, name='category_list'),
    path('add/', views.category_create, name='category_create'),
    path('<int:pk>/edit/', views.category_update, name='category_update'),
    path('<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Livres
    path('books/', views.book_list, name='book_list'),
    path('books/add/', views.book_create, name='book_create'),
    path('books/<int:pk>/edit/', views.book_update, name='book_update'),
    path('books/<int:pk>/delete/', views.book_delete, name='book_delete'),

    #Import Excel file
    path('books/import', views.book_import, name='book_import'),
    path('books/report', views.report_view, name='report_view')
]
