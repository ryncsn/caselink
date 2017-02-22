from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from .models import *


class LinkageSerializer(serializers.ModelSerializer):
    def validate_autocase_pattern(self, data):
        if settings.CASELINK['401_ON_INVALID_PATTERN']:
            # TODO: avoid creating new instead of deleting old
            all_data = self.initial_data
            linkage = Linkage.objects.filter(
                autocase_pattern=data,
                workitem=all_data['workitem']
            )
            if len(linkage) == 1:
                linkage[0].delete()

            for case in AutoCase.objects.all():
                if test_pattern_match(data, case.id):
                    return data
            raise serializers.ValidationError("Pattern Invalid.")
        else:
            return data

    class Meta:
        fields = '__all__'
        model = Linkage


class WorkItemSerializer(serializers.ModelSerializer):
    linkages = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    blacklist_entries = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    patterns = serializers.SerializerMethodField()

    def get_patterns(self, wi):
        return [link.autocase_pattern for link in wi.linkages.all()]

    class Meta:
        fields = '__all__'
        model = WorkItem


class AutoCaseSerializer(serializers.ModelSerializer):
    linkages = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    autocase_failures = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    class Meta:
        fields = '__all__'
        model = AutoCase


class WorkItemLinkageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Linkage
        exclude = ('workitem',)


class BugSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Bug


class AutoCaseFailureSerializer(serializers.ModelSerializer):
    blacklist_entries = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    class Meta:
        fields = '__all__'
        model = AutoCaseFailure


class BlackListEntrySerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = BlackListEntry


class FrameworkSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Framework


class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Component


class ArchSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Arch
