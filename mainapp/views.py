from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import AnalyzedString
from .serializers import AnalyzedStringSerializer
import hashlib
import re
from django.db import IntegrityError, DatabaseError

# Limits
MAX_TEXT_LENGTH = 1024 * 1024  # 1MB limit for input string


def analyze_string(value: str) -> dict:
    """Analyze the string and return its properties."""
    # normalize for palindrome check: remove non-alphanumeric and lowercase
    normalized = re.sub(r'[^0-9a-zA-Z]', '', value).lower()
    is_palindrome = normalized == normalized[::-1]

    length = len(value)
    unique_characters = len(set(value))
    word_count = len(value.split())
    sha256_hash = hashlib.sha256(value.encode()).hexdigest()

    return {
        "length": length,
        "is_palindrome": is_palindrome,
        "unique_characters": unique_characters,
        "word_count": word_count,
        "sha256_hash": sha256_hash,
    }


@api_view(['POST'])
def create_string(request):
    """Create and analyze a new string."""
    value = request.data.get('value', None)

    # Validate presence
    if value is None:
        return Response(
            {"error": "Missing required field: 'value'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate type
    if not isinstance(value, str):
        return Response(
            {"error": "'value' must be a string"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Validate length
    if len(value) == 0:
        return Response(
            {"error": "'value' must not be empty"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    if len(value.encode('utf-8')) > MAX_TEXT_LENGTH:
        return Response(
            {"error": "Input too large"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    sha256_hash = hashlib.sha256(value.encode()).hexdigest()

    # Check for existing string
    if AnalyzedString.objects.filter(sha256_hash=sha256_hash).exists():
        return Response(
            {"error": "String already exists in the system"},
            status=status.HTTP_409_CONFLICT
        )

    # Analyze the string
    properties = analyze_string(value)

    try:
        analyzed_string = AnalyzedString(
            value=value,
            length=properties['length'],
            is_palindrome=properties['is_palindrome'],
            unique_characters=properties['unique_characters'],
            word_count=properties['word_count'],
            sha256_hash=sha256_hash,
        )
        analyzed_string.save()
    except (IntegrityError, DatabaseError) as e:
        # Database-level failure
        return Response(
            {"error": "Failed to save analyzed string", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Create character frequency map (case-sensitive)
    character_frequency_map = {char: value.count(char) for char in set(value)}

    response_data = {
        "id": sha256_hash,
        "value": value,
        "properties": {
            "length": properties['length'],
            "is_palindrome": properties['is_palindrome'],
            "unique_characters": properties['unique_characters'],
            "word_count": properties['word_count'],
            "sha256_hash": sha256_hash,
            "character_frequency_map": character_frequency_map,
        },
        "created_at": analyzed_string.created_at.isoformat(),
    }

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_single_string(request, string_value):
    """Retrieve a specific analyzed string by exact value (URL-decoded by Django)."""
    try:
        analyzed_string = AnalyzedString.objects.get(value=string_value)
    except AnalyzedString.DoesNotExist:
        return Response({"error": "String does not exist in the system"}, status=status.HTTP_404_NOT_FOUND)

    serializer = AnalyzedStringSerializer(analyzed_string)
    return Response({
        "id": analyzed_string.sha256_hash,
        "value": analyzed_string.value,
        "properties": serializer.data,
        "created_at": analyzed_string.created_at.isoformat()
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_all_strings(request):
    """Retrieve all analyzed strings with optional filtering."""
    # Get query parameters
    is_palindrome = request.query_params.get('is_palindrome', None)
    min_length = request.query_params.get('min_length', None)
    max_length = request.query_params.get('max_length', None)
    word_count = request.query_params.get('word_count', None)
    contains_character = request.query_params.get('contains_character', None)

    strings = AnalyzedString.objects.all()

    # Apply filters
    if is_palindrome is not None:
        strings = strings.filter(is_palindrome=(is_palindrome.lower() == 'true'))

    if min_length is not None:
        try:
            strings = strings.filter(length__gte=int(min_length))
        except ValueError:
            return Response({"error": "min_length must be an integer"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    if max_length is not None:
        try:
            strings = strings.filter(length__lte=int(max_length))
        except ValueError:
            return Response({"error": "max_length must be an integer"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    if word_count is not None:
        try:
            strings = strings.filter(word_count=int(word_count))
        except ValueError:
            return Response({"error": "word_count must be an integer"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    if contains_character is not None:
        strings = strings.filter(value__icontains=contains_character)

    serializer = AnalyzedStringSerializer(strings, many=True)
    return Response({
        "data": serializer.data,
        "count": strings.count(),
        "filters_applied": {
            "is_palindrome": is_palindrome,
            "min_length": min_length,
            "max_length": max_length,
            "word_count": word_count,
            "contains_character": contains_character
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def filter_by_natural_language(request):
    """Filter strings based on a natural language query."""
    query = request.query_params.get('query', None)
    if not query:
        return Response({"error": "No query provided"}, status=status.HTTP_400_BAD_REQUEST)

    # Initialize filters
    filters = {
        "is_palindrome": None,
        "min_length": None,
        "max_length": None,
        "word_count": None,
        "contains_character": None,
    }

    # Simple parsing rules (case-insensitive)
    q_lower = query.lower()

    if "palindrome" in q_lower:
        filters["is_palindrome"] = True

    if "single word" in q_lower or re.search(r'\bonly one word\b', q_lower):
        filters["word_count"] = 1

    if match := re.search(r'longer than (\d+) characters?', q_lower):
        filters["min_length"] = int(match.group(1))

    if match := re.search(r'shorter than (\d+) characters?', q_lower):
        filters["max_length"] = int(match.group(1))

    if match := re.search(r'containing the letter (\w)', q_lower):
        filters["contains_character"] = match.group(1)

    # Retrieve all strings and apply filters
    strings = AnalyzedString.objects.all()

    if filters["is_palindrome"] is not None:
        strings = strings.filter(is_palindrome=filters["is_palindrome"])

    if filters["min_length"] is not None:
        strings = strings.filter(length__gte=filters["min_length"])

    if filters["max_length"] is not None:
        strings = strings.filter(length__lte=filters["max_length"])

    if filters["word_count"] is not None:
        strings = strings.filter(word_count=filters["word_count"])

    if filters["contains_character"] is not None:
        strings = strings.filter(value__icontains=filters["contains_character"])

    serializer = AnalyzedStringSerializer(strings, many=True)
    return Response({
        "data": serializer.data,
        "count": strings.count(),
        "interpreted_query": {
            "original": query,
            "parsed_filters": filters
        }
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
def delete_string(request, string_value):
    """Delete a specific analyzed string."""
    try:
        analyzed_string = AnalyzedString.objects.get(value=string_value)
    except AnalyzedString.DoesNotExist:
        return Response({"error": "String does not exist in the system"}, status=status.HTTP_404_NOT_FOUND)

    analyzed_string.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)