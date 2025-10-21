from rest_framework import serializers
from .models import AnalyzedString

class AnalyzedStringSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyzedString
        fields = '__all__'