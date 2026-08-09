from django.urls import path
from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("search", views.search, name="search"),
    path("products/<int:product_id>/", views.product_detail, name="product-detail"),
]
