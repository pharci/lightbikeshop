from django.urls import include, re_path, path

from . import views

urlpatterns = [
	#Leave as empty string for base url
	path('', views.news, name="news"),
	path('faq/', views.faq, name="faq"),
]