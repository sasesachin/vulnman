from rest_framework import serializers
from apps.projects import models
from apps.networking.models import Service


class ProjectSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField()
    vulnerabilities = serializers.PrimaryKeyRelatedField(source="vulnerability_set", read_only=True, many=True)
    hosts = serializers.PrimaryKeyRelatedField(source="host_set", read_only=True, many=True)
    services = serializers.SerializerMethodField()

    def get_services(self, obj):
        return Service.objects.filter(host__project=obj).values_list('pk', flat=True)

    class Meta:
        model = models.Project
        fields = '__all__'
        read_only_fields = ["uuid", "creator", "vulnerabilities"]
