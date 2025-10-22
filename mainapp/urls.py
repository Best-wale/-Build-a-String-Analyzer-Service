from django.urls import path
from . import views

urlpatterns = [
    path('strings/', views.strings_view, name='strings'),  # GET, POST, DELETE
    path('strings/<str:string_value>/', views.string_detail_view, name='string-detail'),  # GET, DELETE
    path('strings/filter-by-natural-language', views.strings_natural_filter_view, name='strings-natural-filter'),  # GET
]
