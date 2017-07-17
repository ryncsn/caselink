import logging
from rest_framework import filters
from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from caselink.models import (
    WorkItem, AutoCase, Linkage, Bug, Arch, BlackListEntry, AutoCaseFailure,
    Framework, Component)
from caselink.serializers import (
    WorkItemSerializer, AutoCaseSerializer, LinkageSerializer,
    BugSerializer, ArchSerializer, BlackListEntrySerializer,
    AutoCaseFailureSerializer, WorkItemLinkageSerializer,
    FrameworkSerializer, ComponentSerializer)
from caselink.utils.jira import Jira


LOGGER = logging.getLogger(__name__)


# Standard RESTful APIs
class WorkItemList(generics.ListCreateAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('title', 'linkages', 'type', 'automation', 'project', 'archs', 'errors')


class WorkItemDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.save()
        if instance.changes and instance.jira_id:
            try:
                if Jira().add_jira_comment(instance.jira_id, instance.changes):
                    instance.changes = None
                    instance.save()
            except Exception:
                LOGGER.error("Failed to add comment for WI %s, Jira task %s",
                             instance.id, instance.jira_id)


class AutoCaseList(generics.ListCreateAPIView):
    queryset = AutoCase.objects.all()
    serializer_class = AutoCaseSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('linkages', 'autocase_failures', 'framework', 'errors', 'pr')


class AutoCaseDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = AutoCase.objects.all()
    serializer_class = AutoCaseSerializer


class LinkageList(generics.ListCreateAPIView):
    queryset = Linkage.objects.all()
    serializer_class = LinkageSerializer
    filter_backends = (filters.DjangoFilterBackend,)


class LinkageDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Linkage.objects.all()
    serializer_class = LinkageSerializer


class AutoCaseFailureList(generics.ListCreateAPIView):
    queryset = AutoCaseFailure.objects.all()
    serializer_class = AutoCaseFailureSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('autocases', 'failure_regex', 'autocase_pattern', 'errors')


class AutoCaseFailureDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = AutoCaseFailure.objects.all()
    serializer_class = AutoCaseFailureSerializer


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
        linkages = self.get_objects(workitem)
        serializers = [LinkageSerializer(caselink) for caselink in linkages]
        return Response(serializer.data for serializer in serializers)

    def post(self, request, workitem, format=None):
        request.data['workitem'] = workitem
        serializer = LinkageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
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
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, workitem, pattern, format=None):
        caselink = self.get_object(workitem, pattern)
        caselink.delete()
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
            return case.linkages.all()
        except Linkage.DoesNotExist:
            raise Http404

    def get(self, request, autocase, format=None):
        linkages = self.get_objects(autocase)
        serializers = [LinkageSerializer(caselink) for caselink in linkages]
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
