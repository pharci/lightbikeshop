from django.urls import include, re_path, path

from . import views

urlpatterns = [
	#Leave as empty string for base url
	path('', views.home, name="home"),
	path('faq/', views.faq, name="faq"),
    path('taobao-parser/', views.taobao_parser, name="taobao_parser"),
    path('taobao-parser/proxy/', views.taobao_parser_proxy, name="taobao_parser_proxy"),
    path('taobao-parser/proxy/<path:path>', views.taobao_parser_proxy),
    path("legal/<slug:slug>/", views.page_detail, name="detail"),
    path("robots.txt", views.robots_txt),
]
