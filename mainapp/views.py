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
    """
    Compute the canonical properties for a string. Normalization removes non-alphanumerics
    and lower-cases the string for palindrome and unique character checks.
    """
    normalized = re.sub(r'[^0-9a-zA-Z]', '', value).lower()
    is_palindrome = normalized == normalized[::-1]
    # unique characters should be computed from the normalized version
    unique_characters = len(set(normalized))
    # word_count should count non-empty runs of non-whitespace characters
    word_count = len(re.findall(r'\S+', value))
    return {
        "length": len(value),
        "is_palindrome": is_palindrome,
        "unique_characters": unique_characters,
        "word_count": word_count,
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

        # Build consistent response entries (same structure as POST response)
        results = []
        for obj in qs:
            props = analyze_string(obj.value)
            results.append({
                "id": obj.sha256_hash,
                "value": obj.value,
                "properties": props,
                "created_at": obj.created_at.isoformat()
            })

        return Response({
            "count": qs.count(),
            "filters_applied": filters,
            "data": results
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
        # Return properties in the same canonical shape as POST
        props = analyze_string(obj.value)
        return Response({
            "id": obj.sha256_hash,
            "value": obj.value,
            "properties": props,
            "created_at": obj.created_at.isoformat()
        }, status=200)

    if request.method == 'DELETE':
        obj.delete()
        return Response(status=204)


@api_view(['GET'])
def strings_natural_filter_view(request):
    """/strings/filter-by-natural-language?query=... (also accepts 'q' param)"""
    # Accept either `query` or `q` to be more flexible
    query = request.query_params.get('query') or request.query_params.get('q')
    if not query:
        return Response({"error": "No query provided"}, status=400)

    filters = {
        "is_palindrome": None,
        "min_length": None,
        "max_length": None,
        "word_count": None,
        "min_word_count": None,
        "max_word_count": None,
        "contains_character": None,
    }

    q = query.lower()

    # Palindrome check (singular or plural)
    if re.search(r'\bpalindrom', q):  # matches palindrome or palindromes
        filters["is_palindrome"] = True

    # Single / one-word checks
    if re.search(r'\b(single[- ]word|only one word|one[- ]word|one word)\b', q):
        filters["word_count"] = 1

    # Word count expressions: exactly N words, at least N words, no more than N words
    if match := re.search(r'\bexactly (\d+) words?\b', q):
        filters["word_count"] = int(match.group(1))
    if match := re.search(r'\bat least (\d+) words?\b', q):
        filters["min_word_count"] = int(match.group(1))
    if match := re.search(r'\b(no more than|at most|no greater than) (\d+) words?\b', q):
        filters["max_word_count"] = int(match.group(2))

    # Length expressions
    # "longer than N characters" -> min_length = N + 1
    if match := re.search(r'\b(?:longer than|more than|greater than) (\d+) characters?\b', q):
        filters["min_length"] = int(match.group(1)) + 1
    # "at least N characters" -> min_length = N
    if match := re.search(r'\bat least (\d+) characters?\b', q):
        filters["min_length"] = int(match.group(1))
    # "shorter than N characters" -> max_length = N - 1
    if match := re.search(r'\bshorter than (\d+) characters?\b', q):
        filters["max_length"] = int(match.group(1)) - 1
    # "less than N characters" -> max_length = N - 1
    if match := re.search(r'\b(?:less than|under) (\d+) characters?\b', q):
        filters["max_length"] = int(match.group(1)) - 1
    # "exactly N characters"
    if match := re.search(r'\bexactly (\d+) characters?\b', q):
        n = int(match.group(1))
        filters["min_length"] = n
        filters["max_length"] = n

    # Contains a character: various phrasings
    if match := re.search(r'(?:containing|contains|with) (?:the )?letter (\w)', q):
        filters["contains_character"] = match.group(1)
    elif match := re.search(r'containing (\w)', q):
        filters["contains_character"] = match.group(1)

    # Build queryset with interpreted filters
    qs = AnalyzedString.objects.all()
    if filters["is_palindrome"] is not None:
        qs = qs.filter(is_palindrome=filters["is_palindrome"])
    if filters["min_length"] is not None:
        qs = qs.filter(length__gte=filters["min_length"])
    if filters["max_length"] is not None:
        qs = qs.filter(length__lte=filters["max_length"])
    if filters["word_count"] is not None:
        qs = qs.filter(word_count=filters["word_count"])
    if filters["min_word_count"] is not None:
        qs = qs.filter(word_count__gte=filters["min_word_count"])
    if filters["max_word_count"] is not None:
        qs = qs.filter(word_count__lte=filters["max_word_count"])
    if filters["contains_character"] is not None:
        qs = qs.filter(value__icontains=filters["contains_character"])

    # Use consistent output structure
    results = []
    for obj in qs:
        props = analyze_string(obj.value)
        results.append({
            "id": obj.sha256_hash,
            "value": obj.value,
            "properties": props,
            "created_at": obj.created_at.isoformat()
        })

    serializer = AnalyzedStringSerializer(qs, many=True)
    return Response({
        "count": qs.count(),
        "interpreted_query": {"original": query, "parsed_filters": filters},
        "data": results
    }, status=200)
