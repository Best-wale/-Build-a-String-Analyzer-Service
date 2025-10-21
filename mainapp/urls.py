from django.urls import path
from .views import create_string, get_single_string, get_all_strings, delete_string, filter_by_natural_language

urlpatterns = [
    path('strings/', create_string, name='create_string'),
    path('strings/<str:string_value>/', get_single_string, name='get_single_string'),
    path('strings/all/', get_all_strings, name='get_all_strings'),
    path('strings/filter-by-natural-language/', filter_by_natural_language, name='filter_by_natural_language'),
    path('strings/<str:string_value>/', delete_string, name='delete_string'),
]