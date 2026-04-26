# HTTP/1.1 Protocol Summary

## Overview

HTTP (Hypertext Transfer Protocol) is a stateless, text-based application-layer protocol for distributed hypermedia (RFC 7230–7235, RFC 9110).  
Default port: 80 (HTTP), 443 (HTTPS).  
Request-response model; each message is independent (stateless) unless cookies/sessions are used.

---

## Request Methods

| Method  | Safe | Idempotent | Description                                |
|---------|------|------------|--------------------------------------------|
| GET     | Yes  | Yes        | Retrieve resource representation           |
| HEAD    | Yes  | Yes        | Same as GET but no body returned           |
| POST    | No   | No         | Submit data; create/update resource        |
| PUT     | No   | Yes        | Replace resource entirely                  |
| DELETE  | No   | Yes        | Remove resource                            |
| OPTIONS | Yes  | Yes        | Query supported methods for resource       |
| PATCH   | No   | No         | Partial modification of resource           |
| CONNECT | No   | No         | Establish tunnel (HTTPS proxy)             |
| TRACE   | Yes  | Yes        | Echo request back for diagnostics          |

---

## Request Format

```
METHOD /path HTTP/1.1\r\n
Host: example.com\r\n
User-Agent: client/1.0\r\n
Accept: */*\r\n
Content-Length: <n>\r\n  (if body)
\r\n
[optional body]
```

---

## Response Format

```
HTTP/1.1 <status-code> <reason-phrase>\r\n
Content-Type: text/html\r\n
Content-Length: <n>\r\n
\r\n
[optional body]
```

---

## Key Status Codes

| Code | Meaning                          |
|------|----------------------------------|
| 200  | OK                               |
| 201  | Created                          |
| 204  | No Content                       |
| 301  | Moved Permanently                |
| 302  | Found (temporary redirect)       |
| 304  | Not Modified                     |
| 400  | Bad Request                      |
| 401  | Unauthorized                     |
| 403  | Forbidden                        |
| 404  | Not Found                        |
| 405  | Method Not Allowed               |
| 408  | Request Timeout                  |
| 409  | Conflict                         |
| 413  | Payload Too Large                |
| 429  | Too Many Requests                |
| 500  | Internal Server Error            |
| 501  | Not Implemented                  |
| 503  | Service Unavailable              |

---

## Important Headers

- `Host` — required in HTTP/1.1; identifies target virtual host
- `Content-Type` — MIME type of body (e.g., `application/json`)
- `Content-Length` — byte length of body; required when body present
- `Transfer-Encoding: chunked` — alternative to Content-Length for streaming
- `Connection: keep-alive / close` — persistent connection control
- `Authorization` — credentials for protected resources
- `Cookie` / `Set-Cookie` — session management
- `Cache-Control` — caching directives
- `Accept` / `Accept-Encoding` — content negotiation
- `Location` — redirect target URI (in 3xx responses)

---

## State Model (Request-Response Cycle)

```
INIT → [TCP connect] → CONNECTED
CONNECTED → [GET /path] → RESPONSE_PENDING
RESPONSE_PENDING → [200 OK] → IDLE
IDLE → [GET /path] → RESPONSE_PENDING  (keep-alive)
IDLE → [POST /data] → RESPONSE_PENDING
CONNECTED → [Connection: close after response] → CLOSED
RESPONSE_PENDING → [401 Unauthorized] → AUTH_REQUIRED
AUTH_REQUIRED → [GET /path + Authorization] → RESPONSE_PENDING
```

---

## Field Constraints & Ordering Rules

1. `Host` header is mandatory in every HTTP/1.1 request
2. `Content-Length` or `Transfer-Encoding` required when request has body
3. `POST`/`PUT`/`PATCH` should include body with `Content-Type`
4. `OPTIONS *` is a server-level options request (path = `*`)
5. `HEAD` response must not include a body
6. Persistent connections (keep-alive) allow multiple requests on one TCP connection
7. `Connection: close` header signals connection will be closed after response
