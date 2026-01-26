from django.urls import path
from admin_panel.views import admin_index

urlpatterns = [
	path("", admin_index, name="admin-index"),
]