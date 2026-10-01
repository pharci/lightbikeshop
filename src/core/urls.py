from django.urls import include, re_path, path
from django.views.generic.base import RedirectView

from . import views

urlpatterns = [
	#Leave as empty string for base url
	path('', views.home, name="home"),
	path('faq/', views.faq, name="faq"),
    path('taobao/', views.taobao_parser_proxy, {"path": ""}, name="taobao_parser"),
    path('taobao/<path:path>', views.taobao_parser_proxy),
    path('taobao-parser/', RedirectView.as_view(pattern_name="core:taobao_parser", query_string=True)),
    path('taobao-parser/proxy/', RedirectView.as_view(pattern_name="core:taobao_parser", query_string=True)),
    path('taobao-parser/<path:path>', views.taobao_parser_proxy),
    path("legal/<slug:slug>/", views.page_detail, name="detail"),
    path("robots.txt", views.robots_txt),
]
