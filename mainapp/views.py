from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import AnalyzedString
from .serializers import AnalyzedStringSerializer
import hashlib
import re

def analyze_string(value):
    """Analyze the string and return its properties."""
    length = len(value)
    is_palindrome = value.lower() == value[::-1].lower()  
    unique_characters = len(set(value))  
    word_count = len(value.split())  # Count words 
    sha256_hash = hashlib.sha256(value.encode()).hexdigest()  
    
    return {
        "length": length,
        "is_palindrome": is_palindrome,
        "unique_characters": unique_characters,
        "word_count": word_count,
        "sha256_hash": sha256_hash,
    }



#----Create string <-----CHECK----

@api_view(['POST'])
def create_string(request):
    """Create and analyze a new string."""
    value = request.data.get('value', None)

    # Validate input
    if not value or not isinstance(value, str):
        return Response({"error": "Invalid request body or missing 'value' field"},
                        status=status.HTTP_400_BAD_REQUEST)
    
    sha256_hash = hashlib.sha256(value.encode()).hexdigest()

    # Check for existing string
    if AnalyzedString.objects.filter(sha256_hash=sha256_hash).exists():
        return Response({"error": "String already exists in the system"},
                        status=status.HTTP_409_CONFLICT)

    # Analyze the string
    properties = analyze_string(value)
    analyzed_string = AnalyzedString(
        value=value,
        length=properties['length'],
        is_palindrome=properties['is_palindrome'],
        unique_characters=properties['unique_characters'],
        word_count=properties['word_count'],
        sha256_hash=sha256_hash,
    )
    analyzed_string.save()

    # Create character frequency map
    character_frequency_map = {char: value.count(char) for char in set(value)}

    # Prepare the response
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
#----GET string by single string <-----CHECK----


@api_view(['GET'])
def get_single_string(request, string_value):
    """Retrieve a specific analyzed string."""
    try:
        analyzed_string = AnalyzedString.objects.get(value=string_value)
        serializer = AnalyzedStringSerializer(analyzed_string)
        return Response({
            "id": analyzed_string.sha256_hash,
            "value": analyzed_string.value,
            "properties": serializer.data,
            "created_at": analyzed_string.created_at.isoformat()
        }, status=status.HTTP_200_OK)

    except AnalyzedString.DoesNotExist:
        return Response({"error": "String does not exist in the system"}, status=status.HTTP_404_NOT_FOUND)







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
        strings = strings.filter(length__gte=int(min_length))

    if max_length is not None:
        strings = strings.filter(length__lte=int(max_length))

    if word_count is not None:
        strings = strings.filter(word_count=word_count)

    if contains_character is not None:
        strings = strings.filter(value__icontains=contains_character)

    # Serialize the results
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

    filters = {
        "is_palindrome": None,
        "min_length": None,
        "word_count": None,
        "contains_character": None,
    }

    # Simple parsing rules
    if "palindrome" in query:
        filters["is_palindrome"] = True
    
    if "single word" in query:
        filters["word_count"] = 1

    if match := re.search(r'longer than (\d+) characters?', query):
        filters["min_length"] = int(match.group(1))
    
    if match := re.search(r'shorter than (\d+) characters?', query):
        filters["max_length"] = int(match.group(1))

    if match := re.search(r'containing the letter (\w)', query):
        filters["contains_character"] = match.group(1)

    # Retrieve strings with applied filters
    strings = AnalyzedString.objects.all()
    if filters["is_palindrome"] is not None:
        strings = strings.filter(is_palindrome=filters["is_palindrome"])
    
    if filters["min_length"] is not None:
        strings = strings.filter(length__gte=filters["min_length"])

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
        analyzed_string.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    except AnalyzedString.DoesNotExist:
        return Response({"error": "String does not exist in the system"},
                        status=status.HTTP_404_NOT_FOUND)

#
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

    # Simple parsing rules
    if "palindrome" in query:
        filters["is_palindrome"] = True
    
    if "single word" in query:
        filters["word_count"] = 1

    if match := re.search(r'longer than (\d+) characters?', query):
        filters["min_length"] = int(match.group(1))
    
    if match := re.search(r'shorter than (\d+) characters?', query):
        filters["max_length"] = int(match.group(1))

    if match := re.search(r'containing the letter (\w)', query):
        filters["contains_character"] = match.group(1)

    # Retrieve all strings with applied filters
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

    # Serialize the results
    serializer = AnalyzedStringSerializer(strings, many=True)
    return Response({
        "data": serializer.data,
        "count": strings.count(),
        "interpreted_query": {
            "original": query,
            "parsed_filters": filters
        }
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
def get_all_strings(request):
    """Retrieve all analyzed strings with optional filtering and searching."""
    
    # Get query parameters
    is_palindrome = request.query_params.get('is_palindrome', None)
    min_length = request.query_params.get('min_length', None)
    max_length = request.query_params.get('max_length', None)
    word_count = request.query_params.get('word_count', None)
    contains_character = request.query_params.get('contains_character', None)

    # Start with all strings
    strings = AnalyzedString.objects.all()

    # Apply filters based on query parameters
    if is_palindrome is not None:
        strings = strings.filter(is_palindrome=(is_palindrome.lower() == 'true'))

    if min_length is not None:
        strings = strings.filter(length__gte=int(min_length))

    if max_length is not None:
        strings = strings.filter(length__lte=int(max_length))

    if word_count is not None:
        strings = strings.filter(word_count=word_count)

    if contains_character is not None:
        strings = strings.filter(value__icontains=contains_character)

    # Serialize the results
    serializer = AnalyzedStringSerializer(strings, many=True)
    response ={
	  	"data": serializer.data, 
	  	"count": strings.count(),
	  	"filters_applied": {
		    "is_palindrome": is_palindrome,
		    "min_length": min_length,
		    "max_length": max_length,
		    "word_count": word_count,
		    "contains_character": contains_character
	  	}

  	}

    return Response(response, status=status.HTTP_200_OK)

@api_view(['DELETE'])
def delete_string(request, string_value):
    """Delete a specific analyzed string."""
    try:
        analyzed_string = AnalyzedString.objects.get(value=string_value)
        analyzed_string.delete()  # Remove from the database
        return Response(status=status.HTTP_204_NO_CONTENT)
    except AnalyzedString.DoesNotExist:
        return Response({"error": "String does not exist in the system"},
                        status=status.HTTP_404_NOT_FOUND)



        # /strings/filter-by-natural-language?query=all%20single%20word%20palindromic%20strings
         # /strings?is_palindrome=true&min_length=5&max_length=20&word_count=2&contains_character=a