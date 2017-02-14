import logging

import django_filters
from rest_framework import filters

from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from caselink.models import *
from caselink.serializers import *
from caselink.utils.jira import add_jira_comment


LOGGER = logging.getLogger(__name__)


# Standard RESTful APIs
class WorkItemList(generics.ListCreateAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('title', 'caselinks', 'type', 'automation', 'project', 'archs', 'errors', 'bugs')

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.error_check(depth=1)


class WorkItemDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.changes and instance.jira_id:
            try:
                if add_jira_comment(instance.jira_id, instance.changes):
                    instance.changes = None
                    instance.save()
            except Exception as error:
                LOGGER.error("Failed to add comment for WI %s, Jira task %s",
                             instance.id, instance.jira_id)
        instance.save()
        instance.error_check(depth=1)


    def perform_destroy(self, instance):
        related = instance.get_related()
        instance.delete()
        for item in related:
            item.error_check(depth=0)


class AutoCaseList(generics.ListCreateAPIView):
    queryset = AutoCase.objects.all()
    serializer_class = AutoCaseSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('caselinks', 'failures', 'framework', 'errors', 'pr')

    def perform_create(self, serializer):
        instance = serializer.save()
        # TODO: ignored autolink list
        instance.autolink()
        instance.error_check(depth=1)


class AutoCaseDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = AutoCase.objects.all()
    serializer_class = AutoCaseSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.autolink()
        instance.error_check(depth=1)

    def perform_destroy(self, instance):
        related = instance.get_related()
        instance.delete()
        for item in related:
            item.error_check(depth=0)

class LinkageList(generics.ListCreateAPIView):
    queryset = Linkage.objects.all()
    serializer_class = LinkageSerializer
    filter_backends = (filters.DjangoFilterBackend,)

    def perform_create(self, serializer):
        # TODO: avoid creating when duplicated
        instance = serializer.save()
        instance.autolink()

        autocases = set(instance.autocases.all())
        for other in instance.workitem.caselinks.all():
            other_autocases = set(other.autocases.all())
            if autocases > other_autocases:
                other.delete()
            if autocases < other_autocases:
                instance.delete()
                return
        instance.error_check(depth=1)


class LinkageDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Linkage.objects.all()
    serializer_class = LinkageSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.autolink()
        instance.error_check(depth=1)

    def perform_destroy(self, instance):
        related = instance.get_related()
        instance.delete()
        for item in related:
            item.error_check(depth=0)


class AutoCaseFailureList(generics.ListCreateAPIView):
    queryset = AutoCaseFailure.objects.all()
    serializer_class = AutoCaseFailureSerializer
    filter_backends = (filters.DjangoFilterBackend,)

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.autolink()
        #instance.error_check(depth=1)


class AutoCaseFailureDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = AutoCaseFailure.objects.all()
    serializer_class = AutoCaseFailureSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.autolink()
        #instance.error_check(depth=1)

    def perform_destroy(self, instance):
        #related = instance.get_related()
        instance.delete()
        #for item in related:
        #    item.error_check(depth=0)


class BugList(generics.ListCreateAPIView):
    queryset = Bug.objects.all()
    serializer_class = BugSerializer
    filter_backends = (filters.DjangoFilterBackend,)


class BugDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Bug.objects.all()
    serializer_class = BugSerializer


class BlackList(generics.ListCreateAPIView):
    queryset = BlackListEntry.objects.all()
    serializer_class = BlackListEntrySerializer
    filter_backends = (filters.DjangoFilterBackend,)


class BlackListDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = BlackListEntry.objects.all()
    serializer_class = BlackListEntrySerializer



# Shortcuts RESTful APIs

class WorkItemLinkageList(APIView):
    """
    Retrieve, update or delete a caselink instance of a workitem.
    """

    # This serializer is only used for html view to hide workitem field
    serializer_class = WorkItemLinkageSerializer
    filter_backends = (filters.DjangoFilterBackend,)

    def get_objects(self, workitem):
        wi = get_object_or_404(WorkItem, id=workitem)
        try:
            return Linkage.objects.filter(workitem=wi)
        except Linkage.DoesNotExist:
            raise Http404

    def get(self, request, workitem, format=None):
        caselinks = self.get_objects(workitem)
        serializers = [LinkageSerializer(caselink) for caselink in caselinks]
        return Response(serializer.data for serializer in serializers)

    def post(self, request, workitem, format=None):
        request.data['workitem'] = workitem
        serializer = LinkageSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            instance.autolink()
            instance.error_check(depth=1)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkItemLinkageDetail(APIView):
    """
    Retrieve, update or delete a caselink instance of a workitem.
    """

    serializer_class = WorkItemLinkageSerializer

    def get_object(self, workitem, pattern):
        wi = get_object_or_404(WorkItem, id=workitem)
        try:
            return Linkage.objects.get(workitem=wi, autocase_pattern=pattern)
        except Linkage.DoesNotExist:
            raise Http404

    def get(self, request, workitem, pattern, format=None):
        caselink = self.get_object(workitem, pattern)
        serializer = LinkageSerializer(caselink)
        return Response(serializer.data)

    def put(self, request, workitem, pattern, format=None):
        request.data['workitem'] = workitem
        caselink = self.get_object(workitem, pattern)
        serializer = LinkageSerializer(caselink, data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            instance.autolink()
            instance.error_check(depth=1)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, workitem, pattern, format=None):
        caselink = self.get_object(workitem, pattern)
        related = caselink.get_related()
        caselink.delete()
        for item in related:
            item.error_check(depth=0)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AutoLinkageageList(APIView):
    """
    Retrieve, update or delete a caselink instance of a autocase.
    """

    serializer_class = LinkageSerializer
    filter_backends = (filters.DjangoFilterBackend,)

    def get_objects(self, autocase):
        case = get_object_or_404(AutoCase, id=autocase)
        try:
            return case.caselinks.all();
        except Linkage.DoesNotExist:
            raise Http404

    def get(self, request, autocase, format=None):
        caselinks = self.get_objects(autocase)
        serializers = [LinkageSerializer(caselink) for caselink in caselinks]
        return Response(serializer.data for serializer in serializers)


# RESTful APIs for meta class
class FrameworkList(generics.ListCreateAPIView):
    queryset = Framework.objects.all()
    serializer_class = FrameworkSerializer
    filter_backends = (filters.DjangoFilterBackend,)

class FrameworkDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Framework.objects.all()
    serializer_class = FrameworkSerializer

class ComponentList(generics.ListCreateAPIView):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    filter_backends = (filters.DjangoFilterBackend,)

class ComponentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer

class ArchList(generics.ListCreateAPIView):
    queryset = Arch.objects.all()
    serializer_class = ArchSerializer
    filter_backends = (filters.DjangoFilterBackend,)

class ArchDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Arch.objects.all()
    serializer_class = ArchSerializer
