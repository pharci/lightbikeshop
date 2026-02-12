from django.urls import include, re_path, path

from . import views

urlpatterns = [
	#Leave as empty string for base url
	path('', views.home, name="home"),
	path('faq/', views.faq, name="faq"),
    path("legal/<slug:slug>/", views.page_detail, name="detail"),
    path("robots.txt", views.robots_txt),
]