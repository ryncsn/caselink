"""caselink URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin
from rest_framework import routers, serializers, viewsets
from caselink.views import views, restful, control

urlpatterns = [
    # Views for nagivation/look up
    url(r'^$', views.index, name='index'),
    url(r'^m2a$', views.m2a, name='m2a'),
    url(r'^a2m$', views.a2m, name='a2m'),
    url(r'^map$', views.linkage_map, name='map'),
    url(r'^black-list$', views.bl, name='a2m'),
    url(r'^data/m2a/((?P<pk>[a-zA-Z0-9\-]+)/)?$', views.m2a_data, name='m2a_data'),
    url(r'^data/a2m/$', views.a2m_data, name='a2m_data'),
    url(r'^data/bl/((?P<pk>[a-zA-Z0-9\-]+)/)?', views.bl_data, name='bl_data'),
    url(r'^pattern-matcher/(?P<pattern>[a-zA-Z0-9\-\._]+)$', views.pattern_matcher, name='pattern-matcher'),

    #RESTful APIs
    url(r'^(manual|workitem)/$', restful.WorkItemList.as_view(), name='workitem'),
    url(r'^(manual|workitem)/(?P<pk>[a-zA-Z0-9\-]+)/$', restful.WorkItemDetail.as_view(), name='workitem_detail'),
    url(r'^(manual|workitem)/(?P<workitem>[a-zA-Z0-9\-\._]+)/(link|linkage)/$', restful.WorkItemLinkageList.as_view(), name='workitem_link_list'),
    url(r'^(manual|workitem)/(?P<workitem>[a-zA-Z0-9\-\._]+)/(link|linkage)/(?P<pattern>[a-zA-Z0-9\-\.\ _]*)/$', restful.WorkItemLinkageDetail.as_view(), name='workitem_link_detail'),

    url(r'^(auto|autocase)/$', restful.AutoCaseList.as_view(), name='auto'),
    url(r'^(auto|autocase)/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.AutoCaseDetail.as_view(), name='auto_detail'),

    url(r'^autocase_failure/$', restful.AutoCaseFailureList.as_view(), name='auto_failure_list'),
    url(r'^autocase_failure/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.AutoCaseFailureDetail.as_view(), name='auto_failure_detail'),

    url(r'^(link|linkage)/$', restful.LinkageList.as_view(), name='link'),
    url(r'^(link|linkage)/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.LinkageDetail.as_view(), name='link_detail'),

    url(r'^bug/$', restful.BugList.as_view(), name='bug'),
    url(r'^bug/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.BugDetail.as_view(), name='bug_detail'),

    url(r'^blacklist/$', restful.BlackList.as_view(), name='bl'),
    url(r'^blacklist/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.BlackListDetail.as_view(), name='bl_detail'),

    url(r'^framework/$', restful.FrameworkList.as_view(), name='framework'),
    url(r'^framework/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.FrameworkDetail.as_view(), name='framework_detail'),

    url(r'^component/$', restful.ComponentList.as_view(), name='component'),
    url(r'^component/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.ComponentDetail.as_view(), name='component_detail'),

    url(r'^arch/$', restful.ArchList.as_view(), name='arch'),
    url(r'^arch/(?P<pk>[a-zA-Z0-9\-\._]+)/$', restful.ArchDetail.as_view(), name='arch_detail'),

    # API for get/start tasks, backup/restore
    url(r'^control/$', control.overview, name='task_overview'),
    url(r'^control/task/$', control.task, name='task_list'),
    url(r'^control/trigger/$', control.trigger, name='task_trigger'),
    url(r'^control/backup/$', control.backup, name='backup_list'),
    url(r'^control/backup/(?P<filename>.+\.yaml)$', control.backup_instance, name='backup_download'),
    url(r'^control/restore/(?P<filename>.+\.yaml)$', control.restore, name='restore'),
    url(r'^control/upload/$', control.upload, name='upload'),
    url(r'^control/maitai_request/$', control.create_maitai_request, name='maitai'),
]
