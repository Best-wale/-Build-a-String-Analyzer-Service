from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import AnalyzedString
from .serializers import AnalyzedStringSerializer
import hashlib
import re
from django.db import IntegrityError, DatabaseError

MAX_TEXT_LENGTH = 1024 * 1024  # 1MB limit


def analyze_string(value: str) -> dict:
    normalized = re.sub(r'[^0-9a-zA-Z]', '', value).lower()
    is_palindrome = normalized == normalized[::-1]
    return {
        "length": len(value),
        "is_palindrome": is_palindrome,
        "unique_characters": len(set(value)),
        "word_count": len(value.split()),
        "sha256_hash": hashlib.sha256(value.encode()).hexdigest(),
    }


@api_view(['GET', 'POST', 'DELETE'])
def strings_view(request):
    """Unified endpoint: /strings"""
    # POST → create new analyzed string
    if request.method == 'POST':
        value = request.data.get('value')
        if value is None:
            return Response({"error": "Missing 'value'"}, status=400)
        if not isinstance(value, str):
            return Response({"error": "'value' must be a string"}, status=422)
        if not value.strip():
            return Response({"error": "'value' must not be empty"}, status=422)
        if len(value.encode('utf-8')) > MAX_TEXT_LENGTH:
            return Response({"error": "Input too large"}, status=422)

        sha256_hash = hashlib.sha256(value.encode()).hexdigest()
        if AnalyzedString.objects.filter(sha256_hash=sha256_hash).exists():
            return Response({"error": "String already exists"}, status=409)

        props = analyze_string(value)
        try:
            analyzed = AnalyzedString.objects.create(
                value=value,
                length=props['length'],
                is_palindrome=props['is_palindrome'],
                unique_characters=props['unique_characters'],
                word_count=props['word_count'],
                sha256_hash=sha256_hash,
            )
        except (IntegrityError, DatabaseError) as e:
            return Response({"error": "Failed to save", "detail": str(e)}, status=500)

        return Response({
            "id": sha256_hash,
            "value": value,
            "properties": props,
            "created_at": analyzed.created_at.isoformat()
        }, status=201)

    # GET → Retrieve all or filtered strings
    if request.method == 'GET':
        qs = AnalyzedString.objects.all()
        filters = {
            "is_palindrome": request.query_params.get('is_palindrome'),
            "min_length": request.query_params.get('min_length'),
            "max_length": request.query_params.get('max_length'),
            "word_count": request.query_params.get('word_count'),
            "contains_character": request.query_params.get('contains_character'),
        }

        if filters["is_palindrome"] is not None:
            qs = qs.filter(is_palindrome=filters["is_palindrome"].lower() == 'true')

        for key in ["min_length", "max_length", "word_count"]:
            val = filters[key]
            if val:
                try:
                    num = int(val)
                    if key == "min_length":
                        qs = qs.filter(length__gte=num)
                    elif key == "max_length":
                        qs = qs.filter(length__lte=num)
                    elif key == "word_count":
                        qs = qs.filter(word_count=num)
                except ValueError:
                    return Response({f"error": f"{key} must be an integer"}, status=422)

        if filters["contains_character"]:
            qs = qs.filter(value__icontains=filters["contains_character"])

        data = AnalyzedStringSerializer(qs, many=True).data
        return Response({
            "count": qs.count(),
            "filters_applied": filters,
            "data": data
        }, status=200)

    # DELETE → Delete all analyzed strings
    if request.method == 'DELETE':
        count, _ = AnalyzedString.objects.all().delete()
        return Response({"deleted": count}, status=204)


@api_view(['GET', 'DELETE'])
def string_detail_view(request, string_value):
    """/strings/<string_value>"""
    try:
        obj = AnalyzedString.objects.get(value=string_value)
    except AnalyzedString.DoesNotExist:
        return Response({"error": "String not found"}, status=404)

    if request.method == 'GET':
        serializer = AnalyzedStringSerializer(obj)
        return Response({
            "id": obj.sha256_hash,
            "value": obj.value,
            "properties": serializer.data,
            "created_at": obj.created_at.isoformat()
        })

    if request.method == 'DELETE':
        obj.delete()
        return Response(status=204)


@api_view(['GET'])
def strings_natural_filter_view(request):
    """/strings/natural-filter?query=..."""
    query = request.query_params.get('query')
    if not query:
        return Response({"error": "No query provided"}, status=400)

    filters = {
        "is_palindrome": None,
        "min_length": None,
        "max_length": None,
        "word_count": None,
        "contains_character": None,
    }

    q = query.lower()

    if "palindrome" in q:
        filters["is_palindrome"] = True
    if "single word" in q or re.search(r'\bonly one word\b', q):
        filters["word_count"] = 1
    if match := re.search(r'longer than (\d+) characters?', q):
        filters["min_length"] = int(match.group(1))
    if match := re.search(r'shorter than (\d+) characters?', q):
        filters["max_length"] = int(match.group(1))
    if match := re.search(r'containing the letter (\w)', q):
        filters["contains_character"] = match.group(1)

    qs = AnalyzedString.objects.all()
    if filters["is_palindrome"] is not None:
        qs = qs.filter(is_palindrome=filters["is_palindrome"])
    if filters["min_length"] is not None:
        qs = qs.filter(length__gte=filters["min_length"])
    if filters["max_length"] is not None:
        qs = qs.filter(length__lte=filters["max_length"])
    if filters["word_count"] is not None:
        qs = qs.filter(word_count=filters["word_count"])
    if filters["contains_character"] is not None:
        qs = qs.filter(value__icontains=filters["contains_character"])

    serializer = AnalyzedStringSerializer(qs, many=True)
    return Response({
        "count": qs.count(),
        "interpreted_query": {"original": query, "parsed_filters": filters},
        "data": serializer.data
    }, status=200)
