API Endpoints (as intended)

Base path: /api

1) Create a string
- URL: POST /api/strings/
- Description: Create and analyze a string (store or process it depending on your implementation).
- Request headers: Content-Type: application/json
- Request body example:
  ```json
  {
    "value": "The quick brown fox jumps over the lazy dog"
  }
  ```
- Success response (example):
  - Status: 201 Created
  ```json
  {
    "value": "The quick brown fox jumps over the lazy dog",
    "analysis_id": "uuid-or-id",
    "word_count": 9,
    "char_count": 43,
    "top_words": [{"word":"the","count":2}, ...]
  }
  ```

2) Get a single string (by value)
- URL: GET /api/strings/<string_value>/
- Description: Retrieve analysis or stored string matching the exact string value (URL-encoded).
- Example:
  GET /api/strings/The%20quick%20brown%20fox%20jumps%20over%20the%20lazy%20dog/
- Success response (example):
  - Status: 200 OK
  ```json
  {
    "value": "The quick brown fox jumps over the lazy dog",
    "analysis_id": "uuid-or-id",
    "word_count": 9,
    "char_count": 43,
    "metadata": {...}
  }
  ```

3) Delete a string
- Intended URL: DELETE /api/strings/<string_value>/
- Description: Delete the stored analysis / record for the given string value.
- Important routing note: Because your URLpattern duplicates the `strings/<str:string_value>/` path, the DELETE view will not be reached if the GET view appears earlier. See the "routing bug" note above.
- Example:
  DELETE /api/strings/The%20quick%20brown%20fox%20jumps%20over%20the%20lazy%20dog/
- Success response:
  - Status: 204 No Content

4) Get all stored strings
- URL: GET /api/strings/all/
- Description: Return a list of all stored strings / analyses.
- Example:
  GET /api/strings/all/
- Success response:
  - Status: 200 OK
  ```json
  {
    "results": [
      {"value": "foo", "analysis_id": "1", "word_count": 1},
      {"value": "bar", "analysis_id": "2", "word_count": 1}
    ]
  }
  ```

5) Filter by natural language
- URL: GET /api/strings/filter-by-natural-language/
- Description: Return strings matching a natural-language query. Query parameters depend on your implementation (e.g., `q`, `lang`, `limit`, etc.)
- Example:
  GET /api/strings/filter-by-natural-language/?q=animals+and+action&limit=10
- Success response:
  - Status: 200 OK
  ```json
  {
    "query": "animals and action",
    "results": [
      {"value": "The quick brown fox", "score": 0.93, ...}
    ]
  }
  ```

---

Common request examples (curl)

- Create
  ```bash
  curl -X POST "https://build-a-string-analyzer-service-production.up.railway.app/api/strings/" \
    -H "Content-Type: application/json" \
    -d '{"value":"Hello world"}'
  ```

- Retrieve
  ```bash
  curl -X GET "https://build-a-string-analyzer-service-production.up.railway.app/api/strings/Hello%20world/"
  ```

- Delete
  ```bash
  curl -X DELETE "https://build-a-string-analyzer-service-production.up.railway.app/api/strings/Hello%20world/"
  ```

- Get all
  ```bash
  curl -X GET "http://localhost:8000/api/strings/all/"
  ```

- Filter (natural language)
  ```bash
  curl -X GET "https://build-a-string-analyzer-service-production.up.railway.app/api/strings/filter-by-natural-language/?q=greetings"
  ```

---

Errors and status codes (recommended)
- 200 OK — successful GET request
- 201 Created — successful POST that creates a resource
- 204 No Content — successful DELETE
- 400 Bad Request — invalid/missing parameters
- 404 Not Found — resource not found
- 409 Conflict — trying to create a duplicate resource
- 422 Unprocessable Entity — input too large or can't be processed
- 500 Internal Server Error — unexpected server error

Return bodies should include an `error` or `detail` field with a human-readable message.

---


